from decimal import Decimal as D

from tests.helpers import add_user, bootstrap, budget_totals, post, register


def sup(client, ctx, name, approve=True):
    s = post(client, ctx["u"]["PROCUREMENT_OFFICER"], "/suppliers", {"name": name}, 201)
    if approve:
        post(client, ctx["h"], f"/suppliers/{s['id']}/approve")
    return s


def stock(client, ctx, qty, cost="1300"):
    post(client, ctx["h"], "/inventory/adjustments", {"warehouse_id": ctx["wh"]["id"], "item_id": ctx["item"]["id"],
                                                      "kind": "OPENING_STOCK", "quantity": qty, "unit_cost": cost,
                                                      "reason": "opening balance"}, 201)


def req(client, ctx, qty, boq=False, submit=True, approve=True):
    line = {"item_id": ctx["item"]["id"], "quantity": qty}
    if boq:
        line["boq_item_id"] = ctx["boq_item"]["id"]
    r = post(client, ctx["u"]["SITE_ENGINEER"], "/requisitions", {
        "project_id": ctx["project"]["id"], "warehouse_id": ctx["wh"]["id"], "lines": [line]}, 201)
    if submit:
        r = post(client, ctx["u"]["SITE_ENGINEER"], f"/requisitions/{r['id']}/submit")
    if approve:
        r = post(client, ctx["u"]["PROJECT_MANAGER"], f"/requisitions/{r['id']}/approve", {"comment": "ok"})
    return r


def quote(client, ctx, r, supplier, rate):
    return post(client, ctx["u"]["PROCUREMENT_OFFICER"], f"/requisitions/{r['id']}/quotes", {
        "supplier_id": supplier["id"], "lines": [{"requisition_line_id": r["lines"][0]["id"], "unit_rate": rate}]}, 201)


def test_full_procure_to_issue_flow(client):
    ctx = bootstrap(client)
    proc, pm, eng, store, h = (ctx["u"]["PROCUREMENT_OFFICER"], ctx["u"]["PROJECT_MANAGER"], ctx["u"]["SITE_ENGINEER"],
                               ctx["u"]["STOREKEEPER"], ctx["h"])
    stock(client, ctx, "180")
    # 1-3: engineer requests 500 bags; system finds a shortage of 320
    r = req(client, ctx, "500", boq=True, approve=False)
    assert D(r["lines"][0]["stock_on_hand"]) == 180 and D(r["lines"][0]["shortage_qty"]) == 320
    assert r["status"] == "SUBMITTED" and r["lines"][0]["exceeds_boq"] is False
    assert client.post(f"/requisitions/{r['id']}/approve", headers=eng, json={}).status_code == 403
    r = post(client, pm, f"/requisitions/{r['id']}/approve", {"comment": "go"})
    # 4-6: quotes, comparison, supplier approval gate
    s1, s2 = sup(client, ctx, "Lucky Cement Dealer"), sup(client, ctx, "Best Traders", approve=False)
    assert client.post(f"/suppliers/{s2['id']}/approve", headers=proc).status_code == 403
    q1, q2 = quote(client, ctx, r, s1, "1300"), quote(client, ctx, r, s2, "1250")
    cmp = client.get(f"/requisitions/{r['id']}/comparison", headers=proc).json()
    tot = {s["supplier"]: (s["total"], s["is_lowest_total"]) for s in cmp["suppliers"]}
    assert D(tot["Lucky Cement Dealer"][0]) == 416000 and D(tot["Best Traders"][0]) == 400000
    assert tot["Best Traders"][1] is True and tot["Lucky Cement Dealer"][1] is False
    assert client.post("/purchase-orders/from-quote", headers=proc, json={"quote_id": q2["id"]}).status_code == 409  # unapproved
    post(client, h, f"/suppliers/{s2['id']}/approve")
    po = post(client, proc, "/purchase-orders/from-quote", {"quote_id": q2["id"]}, 201)
    assert po["status"] == "DRAFT" and D(po["total_amount"]) == 400000 and D(po["lines"][0]["quantity"]) == 320
    assert client.post("/purchase-orders/from-quote", headers=proc, json={"quote_id": q1["id"]}).status_code == 409  # one PO per req
    # 7: approval limit routing - PM (limit 50,000) cannot, owner can
    post(client, proc, f"/purchase-orders/{po['id']}/submit")
    denied = client.post(f"/purchase-orders/{po['id']}/approve", headers=pm, json={})
    assert denied.status_code == 403 and "approval limit" in denied.json()["detail"]
    assert D(budget_totals(client, ctx)["committed"]) == 0
    po = post(client, h, f"/purchase-orders/{po['id']}/approve", {"comment": "approved"})
    assert po["status"] == "APPROVED"
    t = budget_totals(client, ctx)
    assert D(t["committed"]) == 400000 and D(t["actual"]) == 0 and D(t["remaining"]) == 1600000
    # 8-10: GRN with a rejected part, then the rest; over-delivery blocked
    line = po["lines"][0]["id"]
    assert client.post("/goods-receipts", headers=eng, json={"po_id": po["id"], "lines": [
        {"po_line_id": line, "quantity_accepted": "1"}]}).status_code == 403
    g1 = post(client, store, "/goods-receipts", {"po_id": po["id"], "delivery_note": "DN-77", "lines": [
        {"po_line_id": line, "quantity_accepted": "300", "quantity_rejected": "20"}]}, 201)
    assert g1["po_status"] == "PARTIALLY_RECEIVED" and g1["number"] == "GRN-00001"
    s = client.get("/inventory/stock", headers=h).json()[0]
    assert D(s["quantity"]) == 480                                        # 180 + 300 accepted (20 rejected not stocked)
    assert D(budget_totals(client, ctx)["actual"]) == 375000              # 300 x 1250
    assert client.post("/goods-receipts", headers=store, json={"po_id": po["id"], "lines": [
        {"po_line_id": line, "quantity_accepted": "30"}]}).status_code == 409
    g2 = post(client, store, "/goods-receipts", {"po_id": po["id"], "lines": [
        {"po_line_id": line, "quantity_accepted": "20"}]}, 201)
    assert g2["po_status"] == "RECEIVED"
    s = client.get("/inventory/stock", headers=h).json()[0]
    assert D(s["quantity"]) == 500 and D(s["avg_cost"]) == D("1268.0000")   # (180*1300 + 320*1250) / 500
    t = budget_totals(client, ctx)
    assert D(t["actual"]) == 400000 == D(t["committed"]) and D(t["paid"]) == 0
    assert client.post("/goods-receipts", headers=store, json={"po_id": po["id"], "lines": [
        {"po_line_id": line, "quantity_accepted": "1"}]}).status_code == 409
    assert client.post(f"/purchase-orders/{po['id']}/cancel", headers=h).status_code == 409
    # 11: engineer issues material; project consumption updates
    post(client, eng, "/inventory/issues", {"warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
                                            "lines": [{"item_id": ctx["item"]["id"], "quantity": "250"}]}, 201)
    c = client.get("/inventory/consumption", headers=h, params={"project_id": ctx["project"]["id"]}).json()[0]
    assert D(c["net_quantity"]) == 250 and D(c["net_cost"]) == D("317000.00")
    actions = {e["action"] for e in client.get("/audit-logs?limit=500", headers=h).json()}
    assert {"requisition.approve", "po.approve", "grn.create", "inventory.issue", "supplier.approve"} <= actions


def test_sufficient_stock_blocks_purchase(client):
    ctx = bootstrap(client)
    stock(client, ctx, "1000")
    r = post(client, ctx["u"]["SITE_ENGINEER"], "/requisitions", {
        "project_id": ctx["project"]["id"], "warehouse_id": ctx["wh"]["id"],
        "lines": [{"item_id": ctx["item"]["id"], "quantity": "500"}]}, 201)
    assert D(r["lines"][0]["shortage_qty"]) == 0
    res = client.post(f"/requisitions/{r['id']}/submit", headers=ctx["u"]["SITE_ENGINEER"])
    assert res.status_code == 409 and "Stock is sufficient" in res.json()["detail"]
    chk = client.get("/requisitions/stock-check", headers=ctx["h"], params={
        "warehouse_id": ctx["wh"]["id"], "item_id": ctx["item"]["id"], "quantity": "1500"}).json()
    assert D(chk["shortage_qty"]) == 500


def test_on_order_quantity_counts_toward_stock(client):
    ctx = bootstrap(client)
    s = sup(client, ctx, "S1")
    r = req(client, ctx, "300")
    po = post(client, ctx["u"]["PROCUREMENT_OFFICER"], "/purchase-orders/from-quote",
              {"quote_id": quote(client, ctx, r, s, "1000")["id"]}, 201)
    post(client, ctx["u"]["PROCUREMENT_OFFICER"], f"/purchase-orders/{po['id']}/submit")
    post(client, ctx["h"], f"/purchase-orders/{po['id']}/approve")
    chk = client.get("/requisitions/stock-check", headers=ctx["h"], params={
        "warehouse_id": ctx["wh"]["id"], "item_id": ctx["item"]["id"], "quantity": "300"}).json()
    assert D(chk["on_order"]) == 300 and D(chk["shortage_qty"]) == 0     # already on order: don't buy twice


def test_po_cannot_exceed_budget_line_or_lack_cost_code(client):
    ctx = bootstrap(client)
    s = sup(client, ctx, "S1")
    proc, h = ctx["u"]["PROCUREMENT_OFFICER"], ctx["h"]
    big = post(client, proc, "/purchase-orders", {"project_id": ctx["project"]["id"], "warehouse_id": ctx["wh"]["id"],
                                                  "supplier_id": s["id"],
                                                  "lines": [{"item_id": ctx["item"]["id"], "quantity": "1500", "unit_rate": "2000"}]}, 201)
    post(client, proc, f"/purchase-orders/{big['id']}/submit")
    r = client.post(f"/purchase-orders/{big['id']}/approve", headers=h, json={})
    assert r.status_code == 409 and "exceed budget line" in r.json()["detail"]
    assert client.get(f"/purchase-orders/{big['id']}", headers=h).json()["status"] == "PENDING_APPROVAL"
    assert D(budget_totals(client, ctx)["committed"]) == 0
    bag = ctx["bag"]
    nocc = post(client, h, "/inventory/items", {"code": "SAND", "name": "Sand", "unit_id": bag}, 201)
    po2 = post(client, proc, "/purchase-orders", {"project_id": ctx["project"]["id"], "warehouse_id": ctx["wh"]["id"],
                                                  "supplier_id": s["id"],
                                                  "lines": [{"item_id": nocc["id"], "quantity": "1", "unit_rate": "10"}]}, 201)
    post(client, proc, f"/purchase-orders/{po2['id']}/submit")
    assert client.post(f"/purchase-orders/{po2['id']}/approve", headers=h, json={}).status_code == 422


def test_reject_and_cancel_release_state(client):
    ctx = bootstrap(client)
    s, proc, h = sup(client, ctx, "S1"), ctx["u"]["PROCUREMENT_OFFICER"], ctx["h"]
    r = req(client, ctx, "100")
    po = post(client, proc, "/purchase-orders/from-quote", {"quote_id": quote(client, ctx, r, s, "1000")["id"]}, 201)
    assert client.get(f"/requisitions/{r['id']}", headers=h).json()["status"] == "ORDERED"
    post(client, proc, f"/purchase-orders/{po['id']}/submit")
    assert client.post(f"/purchase-orders/{po['id']}/reject", headers=h, json={"comment": ""}).status_code == 422
    post(client, h, f"/purchase-orders/{po['id']}/reject", {"comment": "too expensive"})
    assert client.get(f"/requisitions/{r['id']}", headers=h).json()["status"] == "APPROVED"   # can be re-quoted
    q2 = quote(client, ctx, r, sup(client, ctx, "S2"), "900")
    po2 = post(client, proc, "/purchase-orders/from-quote", {"quote_id": q2["id"]}, 201)
    post(client, proc, f"/purchase-orders/{po2['id']}/submit")
    post(client, h, f"/purchase-orders/{po2['id']}/approve")
    assert D(budget_totals(client, ctx)["committed"]) == 90000
    assert client.post(f"/purchase-orders/{po2['id']}/cancel", headers=proc).status_code == 403   # approved: approver only
    post(client, h, f"/purchase-orders/{po2['id']}/cancel")
    assert D(budget_totals(client, ctx)["committed"]) == 0


def test_boq_check_and_price_anomaly(client):
    ctx = bootstrap(client)
    s, proc, h = sup(client, ctx, "S1"), ctx["u"]["PROCUREMENT_OFFICER"], ctx["h"]
    assert req(client, ctx, "1100", boq=True, approve=False)["lines"][0]["exceeds_boq"] is True    # BOQ has 1000 bags
    r = req(client, ctx, "300")
    po = post(client, proc, "/purchase-orders/from-quote", {"quote_id": quote(client, ctx, r, s, "1000")["id"]}, 201)
    post(client, proc, f"/purchase-orders/{po['id']}/submit")
    post(client, h, f"/purchase-orders/{po['id']}/approve")
    r2 = req(client, ctx, "400")
    quote(client, ctx, r2, s, "1200")
    q = client.get(f"/requisitions/{r2['id']}/comparison", headers=h).json()["lines"][0]
    assert D(q["last_purchase_rate"]) == 1000 and q["quotes"][0]["price_anomaly"] is True       # +20% > 10%
    s2 = sup(client, ctx, "S2")
    quote(client, ctx, r2, s2, "1050")
    q = client.get(f"/requisitions/{r2['id']}/comparison", headers=h).json()["lines"][0]
    flags = {x["supplier"]: x["price_anomaly"] for x in q["quotes"]}
    assert flags == {"S1": True, "S2": False}


def test_procurement_tenant_isolation_and_rbac(client):
    ctx = bootstrap(client)
    s = sup(client, ctx, "S1")
    r = req(client, ctx, "100")
    hb = register(client, "Beta", "b@beta.pk")
    for url in (f"/requisitions/{r['id']}", f"/requisitions/{r['id']}/comparison"):
        assert client.get(url, headers=hb).status_code == 404
    assert client.post(f"/requisitions/{r['id']}/approve", headers=hb, json={}).status_code == 404
    assert client.post(f"/suppliers/{s['id']}/approve", headers=hb).status_code == 404
    assert client.get("/suppliers", headers=hb).json() == [] and client.get("/purchase-orders", headers=hb).json() == []
    cross = client.post("/requisitions", headers=hb, json={"project_id": ctx["project"]["id"],
                                                           "warehouse_id": ctx["wh"]["id"],
                                                           "lines": [{"item_id": ctx["item"]["id"], "quantity": "1"}]})
    assert cross.status_code == 422
    worker = add_user(client, ctx["h"], "w@alpha.pk", "WORKER")
    assert client.get("/suppliers", headers=worker).status_code == 403
    assert client.post("/suppliers", headers=ctx["u"]["SITE_ENGINEER"], json={"name": "Nope"}).status_code == 403
