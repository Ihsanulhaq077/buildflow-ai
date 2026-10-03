from decimal import Decimal as D

from tests.helpers import add_user, bootstrap, post, register


def bal(client, ctx, wh=None):
    r = client.get("/inventory/stock", headers=ctx["h"], params={"warehouse_id": (wh or ctx["wh"])["id"]}).json()
    return r[0] if r else None


def adj(client, ctx, kind, qty, cost=None, h=None, expect=201):
    body = {"warehouse_id": ctx["wh"]["id"], "item_id": ctx["item"]["id"], "kind": kind, "quantity": qty,
            "reason": "test movement"}
    if cost:
        body["unit_cost"] = cost
    return post(client, h or ctx["h"], "/inventory/adjustments", body, expect)


def test_weighted_average_and_ledger_reconciles(client):
    ctx = bootstrap(client)
    adj(client, ctx, "OPENING_STOCK", "100", "1000")
    adj(client, ctx, "INCREASE", "100")                      # at current average
    adj(client, ctx, "OPENING_STOCK", "100", "1200")
    b = bal(client, ctx)
    assert D(b["quantity"]) == 300 and D(b["avg_cost"]) == D("1066.6667")
    issue = post(client, ctx["u"]["SITE_ENGINEER"], "/inventory/issues", {
        "warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
        "lines": [{"item_id": ctx["item"]["id"], "quantity": "50"}]}, 201)
    assert issue["number"] == "ISS-00001" and D(issue["lines"][0]["unit_cost"]) == D("1066.6667")
    post(client, ctx["u"]["SITE_ENGINEER"], "/inventory/returns", {
        "warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
        "lines": [{"item_id": ctx["item"]["id"], "quantity": "10"}]}, 201)
    adj(client, ctx, "DAMAGE", "5")
    adj(client, ctx, "WASTE", "5")
    adj(client, ctx, "DECREASE", "10")
    b = bal(client, ctx)
    ledger = client.get("/inventory/transactions", headers=ctx["h"], params={"item_id": ctx["item"]["id"]}).json()
    assert D(b["quantity"]) == sum(D(t["quantity"]) for t in ledger) == 300 - 50 + 10 - 5 - 5 - 10
    assert D(b["avg_cost"]) == D("1066.6667")                # outbound movements never change the average
    assert {t["type"] for t in ledger} >= {"OPENING_STOCK", "ADJUSTMENT", "MATERIAL_ISSUE", "MATERIAL_RETURN", "DAMAGE", "WASTE"}


def test_insufficient_stock_is_atomic(client):
    ctx = bootstrap(client)
    adj(client, ctx, "OPENING_STOCK", "10", "1000")
    body = {"warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
            "lines": [{"item_id": ctx["item"]["id"], "quantity": "4"}, {"item_id": ctx["item"]["id"], "quantity": "9"}]}
    r = client.post("/inventory/issues", headers=ctx["u"]["STOREKEEPER"], json=body)
    assert r.status_code == 409 and "Insufficient" in r.json()["detail"]
    assert D(bal(client, ctx)["quantity"]) == 10                         # first line rolled back too
    ok = post(client, ctx["u"]["STOREKEEPER"], "/inventory/issues", {**body, "lines": body["lines"][:1]}, 201)
    assert ok["number"] == "ISS-00001"                                   # failed attempt left no gap


def test_transfer_moves_cost_and_project_store_rule(client):
    ctx = bootstrap(client)
    adj(client, ctx, "OPENING_STOCK", "100", "1300")
    other = post(client, ctx["h"], "/warehouses", {"name": "Central Store"}, 201)
    post(client, ctx["u"]["STOREKEEPER"], "/inventory/transfers", {
        "from_warehouse_id": ctx["wh"]["id"], "to_warehouse_id": other["id"],
        "lines": [{"item_id": ctx["item"]["id"], "quantity": "40"}]}, 201)
    assert D(bal(client, ctx)["quantity"]) == 60
    assert D(bal(client, ctx, other)["quantity"]) == 40 and D(bal(client, ctx, other)["avg_cost"]) == 1300
    # a warehouse tied to another project cannot issue to this project
    p2 = post(client, ctx["h"], "/projects", {"code": "P2", "name": "Other"}, 201)
    r = client.post("/inventory/issues", headers=ctx["u"]["STOREKEEPER"], json={
        "warehouse_id": ctx["wh"]["id"], "project_id": p2["id"],
        "lines": [{"item_id": ctx["item"]["id"], "quantity": "1"}]})
    assert r.status_code == 422
    assert client.post("/inventory/transfers", headers=ctx["h"], json={
        "from_warehouse_id": other["id"], "to_warehouse_id": other["id"],
        "lines": [{"item_id": ctx["item"]["id"], "quantity": "1"}]}).status_code == 422


def test_rbac_and_validation(client):
    ctx = bootstrap(client)
    adj(client, ctx, "OPENING_STOCK", "10", "1000")
    assert adj(client, ctx, "DAMAGE", "1", h=ctx["u"]["STOREKEEPER"], expect=403)   # storekeeper cannot adjust
    assert adj(client, ctx, "OPENING_STOCK", "1", h=ctx["h"], expect=422)           # cost required
    r = client.post("/inventory/adjustments", headers=ctx["h"], json={
        "warehouse_id": ctx["wh"]["id"], "item_id": ctx["item"]["id"], "kind": "WASTE", "quantity": "1", "reason": "x"})
    assert r.status_code == 422                                                       # reason required
    assert client.post("/inventory/transfers", headers=ctx["u"]["SITE_ENGINEER"], json={}).status_code == 403
    hr = add_user(client, ctx["h"], "hr@alpha.pk", "HR_ADMIN")
    assert client.get("/inventory/stock", headers=hr).status_code == 403
    assert client.post("/inventory/issues", headers=ctx["u"]["SITE_ENGINEER"], json={
        "warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
        "lines": [{"item_id": ctx["item"]["id"], "quantity": "0"}]}).status_code == 422


def test_reorder_flag_and_consumption(client):
    ctx = bootstrap(client)
    adj(client, ctx, "OPENING_STOCK", "150", "1000")
    assert bal(client, ctx)["below_reorder"] is False
    eng = ctx["u"]["SITE_ENGINEER"]
    post(client, eng, "/inventory/issues", {"warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
                                            "lines": [{"item_id": ctx["item"]["id"], "quantity": "60"}]}, 201)
    post(client, eng, "/inventory/returns", {"warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
                                             "lines": [{"item_id": ctx["item"]["id"], "quantity": "10"}]}, 201)
    assert bal(client, ctx)["below_reorder"] is True                                  # 100 <= 100
    c = client.get("/inventory/consumption", headers=ctx["h"], params={"project_id": ctx["project"]["id"]}).json()[0]
    assert D(c["issued"]) == 60 and D(c["returned"]) == 10 and D(c["net_quantity"]) == 50
    assert D(c["net_cost"]) == D("50000.00")


def test_inventory_tenant_isolation(client):
    ctx = bootstrap(client)
    adj(client, ctx, "OPENING_STOCK", "10", "1000")
    hb = register(client, "Beta", "b@beta.pk")
    assert client.get("/inventory/stock", headers=hb).json() == []
    assert client.get("/inventory/transactions", headers=hb).json() == []
    assert client.get("/warehouses", headers=hb).json() == []
    r = client.post("/inventory/issues", headers=hb, json={
        "warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
        "lines": [{"item_id": ctx["item"]["id"], "quantity": "1"}]})
    assert r.status_code == 422
    assert client.get("/inventory/consumption", headers=hb, params={"project_id": ctx["project"]["id"]}).status_code == 404
