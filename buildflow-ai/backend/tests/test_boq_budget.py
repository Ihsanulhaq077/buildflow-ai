from decimal import Decimal as D

from tests.helpers import add_user, cost_code, item, mk_project, register, unit_id


def setup_boq(client, h, with_codes=True):
    p = mk_project(client, h, contract_value="4000")
    boq = client.post("/boqs", headers=h, json={"project_id": p["id"], "name": "Main BOQ", "overhead_pct": "10",
                                                 "contingency_pct": "5", "profit_pct": "10"}).json()
    cft, ldy = unit_id(client, h, "CFT"), unit_id(client, h, "LDAY")
    mat = cost_code(client, h, "C-MAT", "MATERIAL") if with_codes else None
    lab = cost_code(client, h, "C-LAB", "LABOUR") if with_codes else None
    a = item(client, h, boq["id"], "A", "100", cft, mat="10", lab="2", eq="1", waste="5", cc=mat)
    b = item(client, h, boq["id"], "B", "50", ldy, lab="20", cc=lab)
    return p, boq, a, b


def test_boq_math_is_exact(client):
    h = register(client, "Alpha", "a@alpha.pk")
    p, boq, a, b = setup_boq(client, h)
    assert D(a["unit_rate"]) == D("13.50") and D(a["amount"]) == D("1350.00")   # 10*1.05 + 2 + 1
    assert D(b["amount"]) == D("1000.00")
    s = client.post(f"/boqs/{boq['id']}/calculate", headers=h).json()
    assert D(s["direct_cost"]) == D("2350.00")
    assert D(s["overhead"]) == D("235.00") and D(s["contingency"]) == D("117.50")
    assert D(s["subtotal"]) == D("2702.50") and D(s["profit"]) == D("270.25")
    assert D(s["selling_price"]) == D("2972.75") and D(s["gross_margin_pct"]) == D("9.09")
    assert D(s["material_cost"]) == D("1050.00") and D(s["labour_cost"]) == D("1200.00")
    assert D(s["equipment_cost"]) == D("100.00")


def test_boq_validation_and_isolation(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    hb = register(client, "Beta", "b@beta.pk")
    p, boq, _, _ = setup_boq(client, ha)
    ub = unit_id(client, hb, "CFT")
    r = client.post(f"/boqs/{boq['id']}/items", headers=ha, json={
        "item_code": "Z", "description": "Other org unit", "quantity": "1", "unit_id": ub})
    assert r.status_code == 422
    cc_b = cost_code(client, hb, "B-CC", "MATERIAL")
    r = client.post(f"/boqs/{boq['id']}/items", headers=ha, json={
        "item_code": "Z2", "description": "Other org code", "quantity": "1",
        "unit_id": unit_id(client, ha), "cost_code_id": cc_b})
    assert r.status_code == 422
    assert client.get(f"/boqs/{boq['id']}", headers=hb).status_code == 404
    assert client.post("/boqs", headers=hb, json={"project_id": p["id"], "name": "Sneaky"}).status_code == 422
    dup = client.post(f"/boqs/{boq['id']}/items", headers=ha, json={
        "item_code": "A", "description": "dup", "quantity": "1", "unit_id": unit_id(client, ha)})
    assert dup.status_code == 409
    assert client.post(f"/boqs/{boq['id']}/items", headers=ha, json={
        "item_code": "N", "description": "neg", "quantity": "-5", "unit_id": unit_id(client, ha)}).status_code == 422


def test_unit_conversions_are_configurable(client):
    h = register(client, "Alpha", "a@alpha.pk")
    bag, ton = unit_id(client, h, "BAG"), unit_id(client, h, "TON")
    r = client.post("/unit-conversions", headers=h, json={"from_unit_id": ton, "to_unit_id": bag, "factor": "20"})
    assert r.status_code == 201
    assert client.post("/unit-conversions", headers=h, json={"from_unit_id": ton, "to_unit_id": bag,
                                                             "factor": "20"}).status_code == 409
    assert client.post("/unit-conversions", headers=h, json={"from_unit_id": ton, "to_unit_id": ton,
                                                             "factor": "1"}).status_code == 422
    assert client.get("/unit-conversions", headers=h).json()[0]["factor"] in ("20", "20.00000000")


def test_boq_approval_locks_edits_and_needs_permission(client):
    h = register(client, "Alpha", "a@alpha.pk")
    pm = add_user(client, h, "pm@alpha.pk", "PROJECT_MANAGER")
    p, boq, a, _ = setup_boq(client, h)
    assert client.post(f"/boqs/{boq['id']}/approve", headers=pm).status_code == 403
    assert client.post(f"/boqs/{boq['id']}/approve", headers=h).status_code == 200
    assert client.patch(f"/boqs/{boq['id']}/items/{a['id']}", headers=h, json={"quantity": "1"}).status_code == 409
    assert client.delete(f"/boqs/{boq['id']}/items/{a['id']}", headers=h).status_code == 409
    assert client.patch(f"/boqs/{boq['id']}", headers=h, json={"name": "New"}).status_code == 409


def test_empty_boq_cannot_be_approved(client):
    h = register(client, "Alpha", "a@alpha.pk")
    p = mk_project(client, h)
    boq = client.post("/boqs", headers=h, json={"project_id": p["id"], "name": "Empty"}).json()
    assert client.post(f"/boqs/{boq['id']}/approve", headers=h).status_code == 422


def test_budget_from_boq_end_to_end(client):
    h = register(client, "Alpha", "a@alpha.pk")
    pm = add_user(client, h, "pm@alpha.pk", "PROJECT_MANAGER")
    p, boq, _, _ = setup_boq(client, h)
    # draft BOQ cannot become a budget
    assert client.post("/budgets/from-boq", headers=pm, json={"boq_id": boq["id"]}).status_code == 409
    client.post(f"/boqs/{boq['id']}/approve", headers=h)
    r = client.post("/budgets/from-boq", headers=pm, json={"boq_id": boq["id"]})
    assert r.status_code == 201, r.text
    b = r.json()
    amounts = {l["description"]: D(l["revised_amount"]) for l in b["lines"]}
    assert amounts["C-MAT - C-MAT name"] == D("1350.00") and amounts["C-LAB - C-LAB name"] == D("1000.00")
    assert amounts["Overhead (from BOQ)"] == D("235.00") and amounts["Contingency (from BOQ)"] == D("117.50")
    t = b["totals"]
    assert D(t["revised"]) == D("2702.50") == D(t["original"])
    assert D(t["committed"]) == D(t["actual"]) == D(t["paid"]) == 0     # separate states, not yet used
    assert D(t["remaining"]) == D("2702.50") and D(t["variance"]) == D("2702.50")
    assert D(t["planned_margin"]) == D("1297.50") and D(t["planned_margin_pct"]) == D("32.44")  # vs contract 4000
    assert client.post("/budgets/from-boq", headers=pm, json={"boq_id": boq["id"]}).status_code == 409  # one per project

    # approval: PM cannot, owner can; original frozen afterwards
    assert client.post(f"/budgets/{b['id']}/approve", headers=pm).status_code == 403
    assert client.post(f"/budgets/{b['id']}/approve", headers=h).status_code == 200
    line = b["lines"][0]
    assert client.patch(f"/budgets/{b['id']}/lines/{line['id']}", headers=pm, json={"amount": "1"}).status_code == 409
    # revision: needs budgets.approve, needs a reason, keeps original
    url = f"/budgets/{b['id']}/lines/{line['id']}/revise"
    assert client.post(url, headers=pm, json={"new_amount": "2000", "reason": "Steel price increase"}).status_code == 403
    assert client.post(url, headers=h, json={"new_amount": "2000", "reason": "x"}).status_code == 422
    r = client.post(url, headers=h, json={"new_amount": "2000", "reason": "Steel price increase"})
    assert r.status_code == 200
    t = r.json()["totals"]
    assert D(t["original"]) == D("2702.50")
    assert D(t["revised"]) == D("2702.50") - D(line["revised_amount"]) + D("2000")
    revs = client.get(f"/budgets/{b['id']}/revisions", headers=h).json()
    assert len(revs) == 1 and revs[0]["reason"] == "Steel price increase"
    assert "budget.revise" in {e["action"] for e in client.get("/audit-logs", headers=h).json()}
    # read endpoint
    got = client.get(f"/projects/{p['id']}/budget", headers=pm)
    assert got.status_code == 200 and got.json()["status"] == "APPROVED"


def test_budget_blocked_when_items_lack_cost_codes(client):
    h = register(client, "Alpha", "a@alpha.pk")
    p, boq, _, _ = setup_boq(client, h, with_codes=False)
    client.post(f"/boqs/{boq['id']}/approve", headers=h)
    r = client.post("/budgets/from-boq", headers=h, json={"boq_id": boq["id"]})
    assert r.status_code == 422 and "A, B" in r.json()["detail"]


def test_budget_is_tenant_isolated(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    hb = register(client, "Beta", "b@beta.pk")
    p, boq, _, _ = setup_boq(client, ha)
    client.post(f"/boqs/{boq['id']}/approve", headers=ha)
    b = client.post("/budgets/from-boq", headers=ha, json={"boq_id": boq["id"]}).json()
    assert client.post("/budgets/from-boq", headers=hb, json={"boq_id": boq["id"]}).status_code == 422
    assert client.get(f"/projects/{p['id']}/budget", headers=hb).status_code == 404
    assert client.post(f"/budgets/{b['id']}/approve", headers=hb).status_code == 404
    assert client.get(f"/budgets/{b['id']}/revisions", headers=hb).status_code == 404
