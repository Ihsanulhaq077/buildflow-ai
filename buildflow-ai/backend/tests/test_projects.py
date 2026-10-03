import uuid

from tests.helpers import PW, add_user, mk_project, register


def test_project_crud_and_tenant_isolation(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    hb = register(client, "Beta", "b@beta.pk")
    p = mk_project(client, ha, contract_value="50000000")
    assert p["status"] == "DRAFT"
    assert [x["id"] for x in client.get("/projects", headers=ha).json()] == [p["id"]]
    assert client.get("/projects", headers=hb).json() == []
    # other tenant sees 404 (indistinguishable from missing), cannot modify
    assert client.get(f"/projects/{p['id']}", headers=hb).status_code == 404
    assert client.patch(f"/projects/{p['id']}", headers=hb, json={"name": "Hacked"}).status_code == 404
    assert client.post(f"/projects/{p['id']}/status", headers=hb, json={"status": "TENDER"}).status_code == 404
    assert client.get(f"/projects/{p['id']}/sites", headers=hb).status_code == 404
    # same code allowed in another org, not twice in the same org
    mk_project(client, hb, code="ABC-01")
    assert client.post("/projects", headers=ha, json={"code": "ABC-01", "name": "Dup"}).status_code == 409


def test_cannot_reference_other_org_client_or_user(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    hb = register(client, "Beta", "b@beta.pk")
    cb = client.post("/clients", headers=hb, json={"name": "Beta Client"}).json()
    ub = client.get("/users/me", headers=hb).json()
    r = client.post("/projects", headers=ha, json={"code": "X", "name": "Proj X", "client_id": cb["id"]})
    assert r.status_code == 422
    r = client.post("/projects", headers=ha, json={"code": "X", "name": "Proj X", "project_manager_id": ub["id"]})
    assert r.status_code == 422


def test_mass_assignment_ignored(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    p = mk_project(client, ha)
    r = client.patch(f"/projects/{p['id']}", headers=ha,
                     json={"name": "Renamed", "organization_id": str(uuid.uuid4()), "status": "CLOSED", "code": "Z"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed" and r.json()["status"] == "DRAFT" and r.json()["code"] == "ABC-01"
    assert client.get(f"/projects/{p['id']}", headers=ha).status_code == 200


def test_status_transitions(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    p = mk_project(client, ha)
    url = f"/projects/{p['id']}/status"
    assert client.post(url, headers=ha, json={"status": "ACTIVE"}).status_code == 409  # DRAFT -> ACTIVE not allowed
    for s in ("TENDER", "APPROVED", "ACTIVE", "ON_HOLD", "ACTIVE", "COMPLETED", "CLOSED"):
        assert client.post(url, headers=ha, json={"status": s}).status_code == 200, s
    assert client.post(url, headers=ha, json={"status": "ACTIVE"}).status_code == 409
    assert client.patch(f"/projects/{p['id']}", headers=ha, json={"name": "Nope"}).status_code == 409


def test_validation_and_delete_rules(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    bad = client.post("/projects", headers=ha, json={"code": "D", "name": "Dates", "start_date": "2026-05-01",
                                                     "planned_end_date": "2026-04-01"})
    assert bad.status_code == 422
    assert client.post("/projects", headers=ha, json={"code": "N", "name": "Neg", "contract_value": "-1"}).status_code == 422
    p = mk_project(client, ha)
    assert client.delete(f"/projects/{p['id']}", headers=ha).status_code == 204
    assert client.get(f"/projects/{p['id']}", headers=ha).status_code == 404
    p2 = mk_project(client, ha, code="P2")
    client.post(f"/projects/{p2['id']}/status", headers=ha, json={"status": "TENDER"})
    assert client.delete(f"/projects/{p2['id']}", headers=ha).status_code == 409


def test_rbac_on_projects(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    eng = add_user(client, ha, "eng@alpha.pk", "SITE_ENGINEER")
    pm = add_user(client, ha, "pm@alpha.pk", "PROJECT_MANAGER")
    cli = add_user(client, ha, "client@alpha.pk", "CLIENT")
    assert client.post("/projects", headers=eng, json={"code": "E", "name": "Eng proj"}).status_code == 403
    p = mk_project(client, pm, code="PM1")
    assert client.get("/projects", headers=eng).status_code == 200
    assert client.get("/projects", headers=cli).status_code == 403  # no org-wide access for clients
    assert client.get(f"/projects/{p['id']}", headers=cli).status_code == 403


def test_sites_contracts_and_audit(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    p = mk_project(client, ha)
    assert client.post(f"/projects/{p['id']}/sites", headers=ha, json={"name": "Main Site"}).status_code == 201
    c = {"contract_no": "C-1", "title": "Main contract", "value": "50000000", "retention_pct": "5"}
    assert client.post(f"/projects/{p['id']}/contracts", headers=ha, json=c).status_code == 201
    assert client.post(f"/projects/{p['id']}/contracts", headers=ha, json=c).status_code == 409
    assert len(client.get(f"/projects/{p['id']}/sites", headers=ha).json()) == 1
    actions = {e["action"] for e in client.get("/audit-logs", headers=ha).json()}
    assert {"project.create", "site.create", "contract.create"} <= actions
