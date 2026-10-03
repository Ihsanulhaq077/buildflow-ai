import uuid

PW = "SuperSecret123"


def register(client, org, email):
    r = client.post("/auth/register-organization", json={
        "organization_name": org, "owner_name": "Owner", "email": email, "password": PW})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add_user(client, owner_h, email, role):
    r = client.post("/users", headers=owner_h, json={"email": email, "full_name": "Test User",
                                                     "password": PW, "role_name": role})
    assert r.status_code == 201, r.text
    tok = client.post("/auth/login", json={"email": email, "password": PW}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def mk_project(client, h, code="ABC-01", **extra):
    r = client.post("/projects", headers=h, json={"code": code, "name": "ABC Plaza", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def unit_id(client, h, code="CFT"):
    return next(u["id"] for u in client.get("/units", headers=h).json() if u["code"] == code)


def cost_code(client, h, code, category):
    r = client.post("/cost-codes", headers=h, json={"code": code, "name": f"{code} name", "category": category})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def item(client, h, boq_id, code, qty, unit, mat="0", lab="0", eq="0", waste="0", cc=None):
    r = client.post(f"/boqs/{boq_id}/items", headers=h, json={
        "item_code": code, "description": f"Item {code}", "quantity": qty, "unit_id": unit, "waste_pct": waste,
        "material_rate": mat, "labour_rate": lab, "equipment_rate": eq, "cost_code_id": cc})
    assert r.status_code == 201, r.text
    return r.json()


def post(client, h, url, body=None, expect=200):
    r = client.post(url, headers=h, json=body or {})
    assert r.status_code == expect, f"{url}: {r.status_code} {r.text}"
    return r.json()


def bootstrap(client, org="Alpha", email="a@alpha.pk", labour=False):
    """Owner + users, an active project with an APPROVED budget (cement line 2,000,000), a project store,
    and a cement inventory item mapped to the cost code."""
    h = register(client, org, email)
    users = {r: add_user(client, h, f"{r.lower()}@{org.lower().replace(' ', '')}.pk", r)
             for r in ("PROJECT_MANAGER", "SITE_ENGINEER", "STOREKEEPER", "PROCUREMENT_OFFICER")}
    p = mk_project(client, h, contract_value="5000000")
    bag = unit_id(client, h, "BAG")
    cc = cost_code(client, h, "C-CEM", "MATERIAL")
    boq = post(client, h, "/boqs", {"project_id": p["id"], "name": "BOQ"}, 201)
    bi = item(client, h, boq["id"], "CEM", "1000", bag, mat="2000", cc=cc)
    lab_cc = None
    if labour:   # adds a 750,000 labour line to the budget
        lab_cc = cost_code(client, h, "C-LAB", "LABOUR")
        item(client, h, boq["id"], "LAB", "500", unit_id(client, h, "LDAY"), lab="1500", cc=lab_cc)
    post(client, h, f"/boqs/{boq['id']}/approve")
    b = post(client, h, "/budgets/from-boq", {"boq_id": boq["id"]}, 201)
    post(client, h, f"/budgets/{b['id']}/approve")
    wh = post(client, h, "/warehouses", {"name": "ABC Site Store", "project_id": p["id"]}, 201)
    it = post(client, h, "/inventory/items", {"code": "CEMENT", "name": "Cement 50kg", "unit_id": bag,
                                              "cost_code_id": cc, "reorder_level": "100"}, 201)
    return dict(h=h, u=users, project=p, wh=wh, item=it, cc=cc, boq_item=bi, bag=bag, budget=b, lab_cc=lab_cc)


def budget_totals(client, ctx):
    return client.get(f"/projects/{ctx['project']['id']}/budget", headers=ctx["h"]).json()["totals"]
