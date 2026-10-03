from decimal import Decimal as D

from tests.helpers import add_user, bootstrap, budget_totals, mk_project, post, register
from app.timeutil import local_today

TODAY = str(local_today())


def worker(client, h, code, rate, ot="0", cc=None, name=None):
    body = {"code": code, "name": name or f"Worker {code}", "trade": "Mason", "daily_rate": rate, "overtime_rate": ot}
    if cc:
        body["cost_code_id"] = cc
    return post(client, h, "/workers", body, 201)


def people(client, ctx):
    ctx["hr"] = add_user(client, ctx["h"], "hr@alpha.pk", "HR_ADMIN")
    ctx["foreman"] = add_user(client, ctx["h"], "fm@alpha.pk", "FOREMAN")
    ctx["acct"] = add_user(client, ctx["h"], "acc@alpha.pk", "ACCOUNTANT")
    return ctx


def sheet(client, h, project_id, entries, date=TODAY, expect=201):
    return post(client, h, "/attendance-sheets", {"project_id": project_id, "work_date": date, "entries": entries}, expect)


def test_wage_rates_hidden_without_cost_permission(client):
    ctx = people(client, bootstrap(client, labour=True))
    w = worker(client, ctx["hr"], "W1", "1500", "250", ctx["lab_cc"])
    assert D(w["daily_rate"]) == 1500                                     # HR can see pay data
    assert client.post("/workers", headers=ctx["foreman"], json={"code": "X", "name": "Nope"}).status_code == 403
    assert client.post("/workers", headers=ctx["hr"], json={"code": "W1", "name": "Dup"}).status_code == 409
    fm = client.get("/workers", headers=ctx["foreman"]).json()[0]
    assert fm["daily_rate"] is None and fm["overtime_rate"] is None       # foreman picks workers but sees no wages
    ac = client.get("/workers", headers=ctx["acct"]).json()[0]
    assert D(ac["daily_rate"]) == 1500
    cem = next(c["id"] for c in client.get("/cost-codes", headers=ctx["h"]).json() if c["category"] == "MATERIAL")
    assert client.post("/workers", headers=ctx["hr"], json={"code": "W3", "name": "Wrong code", "cost_code_id": cem}).status_code == 422
    assert client.patch(f"/workers/{w['id']}", headers=ctx["hr"], json={"daily_rate": "1600"}).status_code == 200
    assert "worker.update" in {e["action"] for e in client.get("/audit-logs?limit=300", headers=ctx["h"]).json()}
    hb = register(client, "Beta", "b@beta.pk")
    assert client.get("/workers", headers=hb).json() == []
    assert client.patch(f"/workers/{w['id']}", headers=hb, json={"daily_rate": "1"}).status_code == 404


def test_cost_math_budget_posting_and_summary(client):
    ctx = people(client, bootstrap(client, labour=True))
    pm, eng, fm = ctx["u"]["PROJECT_MANAGER"], ctx["u"]["SITE_ENGINEER"], ctx["foreman"]
    a = worker(client, ctx["hr"], "A", "1500", "250", ctx["lab_cc"])
    b = worker(client, ctx["hr"], "B", "1333.33", "200", ctx["lab_cc"])
    c = worker(client, ctx["hr"], "C", "1000", "0", ctx["lab_cc"])
    pid = ctx["project"]["id"]
    s = sheet(client, fm, pid, [{"worker_id": a["id"], "status": "PRESENT", "overtime_hours": "2"},
                                {"worker_id": b["id"], "status": "HALF_DAY"},
                                {"worker_id": c["id"], "status": "ABSENT"}])
    assert s["total_cost"] is None and all(e["cost"] is None for e in s["entries"])      # foreman: no pay data
    assert (s["present"], s["half_day"], s["absent"]) == (1, 1, 1) and D(s["total_days"]) == D("1.5")
    seen = client.get(f"/attendance-sheets/{s['id']}", headers=pm).json()
    costs = {e["worker_code"]: D(e["cost"]) for e in seen["entries"]}
    assert costs == {"A": D("2000.00"), "B": D("666.67"), "C": D("0.00")}                  # 1333.33/2 = 666.665 -> half-up
    assert D(seen["total_cost"]) == D("2666.67")
    post(client, fm, f"/attendance-sheets/{s['id']}/submit")
    for who in (fm, eng):
        assert client.post(f"/attendance-sheets/{s['id']}/approve", headers=who).status_code == 403
    assert D(budget_totals(client, ctx)["actual"]) == 0                                   # nothing posted before approval
    ap = post(client, pm, f"/attendance-sheets/{s['id']}/approve")
    assert ap["status"] == "APPROVED"
    t = budget_totals(client, ctx)
    assert D(t["actual"]) == D("2666.67") == D(t["committed"])                  # labour has no PO: both move together
    assert D(t["remaining"]) == D("2750000") - D("2666.67") and D(t["committed"]) >= D(t["actual"])
    assert client.post(f"/attendance-sheets/{s['id']}/approve", headers=pm).status_code == 409
    assert client.put(f"/attendance-sheets/{s['id']}/entries", headers=fm, json={"entries": []}).status_code == 409
    sm = client.get("/labour/cost-summary", headers=pm, params={"project_id": pid}).json()
    assert D(sm["total"]) == D("2666.67")
    assert {r["code"]: D(r["amount"]) for r in sm["by_cost_code"]} == {"C-LAB": D("2666.67")}
    assert {r["worker_code"]: (D(r["days"]), D(r["amount"])) for r in sm["by_worker"]}["B"] == (D("0.5"), D("666.67"))
    assert client.get("/labour/cost-summary", headers=fm, params={"project_id": pid}).status_code == 403
    assert client.get("/labour/cost-summary", headers=ctx["acct"], params={"project_id": pid}).status_code == 200
    acts = {e["action"] for e in client.get("/audit-logs?limit=300", headers=ctx["h"]).json()}
    assert {"attendance.create", "attendance.submit", "attendance.approve"} <= acts


def test_validation_rules(client):
    ctx = people(client, bootstrap(client, labour=True))
    fm, pm, pid = ctx["foreman"], ctx["u"]["PROJECT_MANAGER"], ctx["project"]["id"]
    a = worker(client, ctx["hr"], "A", "1500", "250", ctx["lab_cc"])
    c = worker(client, ctx["hr"], "C", "1000", "0", ctx["lab_cc"])
    off = worker(client, ctx["hr"], "OFF", "1000", "0", ctx["lab_cc"])
    client.patch(f"/workers/{off['id']}", headers=ctx["hr"], json={"is_active": False})
    bad = lambda entries: client.post("/attendance-sheets", headers=fm, json={"project_id": pid, "work_date": TODAY, "entries": entries})  # noqa: E731
    assert bad([{"worker_id": a["id"], "status": "ABSENT", "overtime_hours": "1"}]).status_code == 422
    assert bad([{"worker_id": c["id"], "status": "PRESENT", "overtime_hours": "1"}]).status_code == 422        # no OT rate
    assert bad([{"worker_id": a["id"], "status": "PRESENT"}, {"worker_id": a["id"], "status": "PRESENT"}]).status_code == 422
    assert bad([{"worker_id": off["id"], "status": "PRESENT"}]).status_code == 422
    assert bad([{"worker_id": a["id"], "status": "PRESENT", "overtime_hours": "17"}]).status_code == 422
    cem = next(x["id"] for x in client.get("/cost-codes", headers=ctx["h"]).json() if x["category"] == "MATERIAL")
    assert bad([{"worker_id": a["id"], "status": "PRESENT", "cost_code_id": cem}]).status_code == 422
    # failed creates leave nothing behind, so the same date is still free
    s = sheet(client, fm, pid, [{"worker_id": a["id"], "status": "PRESENT"}])
    assert client.post("/attendance-sheets", headers=fm, json={"project_id": pid, "work_date": TODAY}).status_code == 409
    empty = sheet(client, fm, pid, [], date="2026-01-01")
    assert client.post(f"/attendance-sheets/{empty['id']}/submit", headers=fm).status_code == 422
    # reject returns it to DRAFT with a reason, then it can be corrected and resubmitted
    post(client, fm, f"/attendance-sheets/{s['id']}/submit")
    assert client.post(f"/attendance-sheets/{s['id']}/reject", headers=pm, json={"comment": ""}).status_code == 422
    r = post(client, pm, f"/attendance-sheets/{s['id']}/reject", {"comment": "Check overtime"})
    assert r["status"] == "DRAFT" and r["decision_comment"] == "Check overtime"
    post(client, fm, f"/attendance-sheets/{s['id']}/submit")


def test_double_booking_and_rate_snapshot(client):
    ctx = people(client, bootstrap(client, labour=True))
    fm, pm, pid = ctx["foreman"], ctx["u"]["PROJECT_MANAGER"], ctx["project"]["id"]
    a = worker(client, ctx["hr"], "A", "1000", "100", ctx["lab_cc"])
    p2 = mk_project(client, ctx["h"], code="P2")["id"]
    s1 = sheet(client, fm, pid, [{"worker_id": a["id"], "status": "HALF_DAY"}])
    sheet(client, fm, p2, [{"worker_id": a["id"], "status": "HALF_DAY"}])                     # 0.5 + 0.5 is fine
    p3 = mk_project(client, ctx["h"], code="P3")["id"]
    r = client.post("/attendance-sheets", headers=fm, json={"project_id": p3, "work_date": TODAY, "entries": [
        {"worker_id": a["id"], "status": "PRESENT"}]})
    assert r.status_code == 409 and "already booked" in r.json()["detail"]
    client.patch(f"/workers/{a['id']}", headers=ctx["hr"], json={"daily_rate": "5000"})        # later wage change...
    seen = client.get(f"/attendance-sheets/{s1['id']}", headers=pm).json()
    assert D(seen["entries"][0]["cost"]) == D("500.00")                                         # ...does not rewrite history


def test_approval_blocked_without_cost_code_or_budget_line(client):
    ctx = people(client, bootstrap(client, labour=False))     # budget has no labour line
    fm, pm, pid = ctx["foreman"], ctx["u"]["PROJECT_MANAGER"], ctx["project"]["id"]
    lab = next((c for c in client.get("/cost-codes", headers=ctx["h"]).json() if c["category"] == "LABOUR"), None)
    assert lab is None
    lab_cc = post(client, ctx["h"], "/cost-codes", {"code": "C-LAB", "name": "Labour", "category": "LABOUR"}, 201)["id"]
    nocc = worker(client, ctx["hr"], "N", "1000")
    s = sheet(client, fm, pid, [{"worker_id": nocc["id"], "status": "PRESENT"}])
    post(client, fm, f"/attendance-sheets/{s['id']}/submit")
    assert client.post(f"/attendance-sheets/{s['id']}/approve", headers=pm).status_code == 422   # pay but no cost code
    post(client, pm, f"/attendance-sheets/{s['id']}/reject", {"comment": "add cost code"})
    client.put(f"/attendance-sheets/{s['id']}/entries", headers=fm, json={"entries": [
        {"worker_id": nocc["id"], "status": "PRESENT", "cost_code_id": lab_cc}]})
    post(client, fm, f"/attendance-sheets/{s['id']}/submit")
    r = client.post(f"/attendance-sheets/{s['id']}/approve", headers=pm)
    assert r.status_code == 409 and "No approved budget line" in r.json()["detail"]
    assert client.get(f"/attendance-sheets/{s['id']}", headers=pm).json()["status"] == "SUBMITTED"   # stays pending, no posting
    assert D(budget_totals(client, ctx)["actual"]) == 0


def test_labour_tenant_isolation(client):
    ctx = people(client, bootstrap(client, labour=True))
    a = worker(client, ctx["hr"], "A", "1000", "0", ctx["lab_cc"])
    s = sheet(client, ctx["foreman"], ctx["project"]["id"], [{"worker_id": a["id"], "status": "PRESENT"}])
    hb = register(client, "Beta", "b@beta.pk")
    assert client.get(f"/attendance-sheets/{s['id']}", headers=hb).status_code == 404
    assert client.post(f"/attendance-sheets/{s['id']}/approve", headers=hb).status_code == 404
    assert client.get("/attendance-sheets", headers=hb).json() == []
    assert client.get("/labour/cost-summary", headers=hb, params={"project_id": ctx["project"]["id"]}).status_code == 404
    pb = mk_project(client, hb, code="B1")["id"]
    assert client.post("/attendance-sheets", headers=hb, json={"project_id": pb, "work_date": TODAY, "entries": [
        {"worker_id": a["id"], "status": "PRESENT"}]}).status_code == 422                          # other org's worker
