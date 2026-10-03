from datetime import timedelta
from decimal import Decimal as D
from io import BytesIO

from pypdf import PdfReader

from app.timeutil import local_today
from tests.helpers import add_user, bootstrap, mk_project, post, register

T = local_today()


def mk_log(client, h, ctx, day, progress=None, expect=201, **extra):
    body = {"project_id": ctx["project"]["id"], "log_date": str(day), "weather": "Sunny, 31C",
            "work_completed": "Columns cast on grid A-C", "progress": progress or [], **extra}
    return post(client, h, "/daily-logs", body, expect)


def prog(ctx, qty):
    return [{"boq_item_id": ctx["boq_item"]["id"], "quantity": qty}]


def overall(client, ctx, **params):
    return D(client.get(f"/projects/{ctx['project']['id']}/progress", headers=ctx["h"], params=params).json()["overall_percent"])


def test_quantity_progress_is_derived_from_submitted_logs(client):
    ctx = bootstrap(client)                       # one BOQ item: cement, 1000 bags
    eng = ctx["u"]["SITE_ENGINEER"]
    d1, d2 = T - timedelta(days=1), T
    l1 = mk_log(client, eng, ctx, d1, prog(ctx, "650"))
    assert D(l1["progress"][0]["percent"]) == D("65.00")           # shown on the draft...
    assert overall(client, ctx) == 0                               # ...but drafts do not count
    post(client, eng, f"/daily-logs/{l1['id']}/submit")
    assert overall(client, ctx) == D("65.00")
    l2 = mk_log(client, eng, ctx, d2, prog(ctx, "450"))
    post(client, eng, f"/daily-logs/{l2['id']}/submit")
    got = client.get(f"/daily-logs/{l2['id']}", headers=eng).json()
    assert D(got["progress"][0]["cumulative"]) == 1100 and D(got["progress"][0]["percent"]) == D("110.00")
    assert overall(client, ctx) == D("100.00")                     # per-item capped at 100% for the overall figure
    assert overall(client, ctx, as_of=str(d1)) == D("65.00")
    item = client.get(f"/projects/{ctx['project']['id']}/progress", headers=eng).json()["items"][0]
    assert D(item["completed"]) == 1100 and D(item["percent"]) == D("110.00")


def test_overall_progress_is_weighted_by_item_amount(client):
    ctx = bootstrap(client, labour=True)          # cement 2,000,000 + labour 750,000
    eng = ctx["u"]["SITE_ENGINEER"]
    l = mk_log(client, eng, ctx, T, prog(ctx, "500"))             # 50% of cement only
    post(client, eng, f"/daily-logs/{l['id']}/submit")
    assert overall(client, ctx) == D("36.36")                     # 50% * 2.0M / 2.75M


def test_workforce_and_materials_are_derived_not_typed(client):
    ctx = bootstrap(client, labour=True)
    h, eng = ctx["h"], ctx["u"]["SITE_ENGINEER"]
    hr = add_user(client, h, "hr@alpha.pk", "HR_ADMIN")
    fm = add_user(client, h, "fm@alpha.pk", "FOREMAN")
    ws = [post(client, hr, "/workers", {"code": c, "name": f"W {c}", "daily_rate": "1000", "cost_code_id": ctx["lab_cc"]}, 201)
          for c in "ABC"]
    post(client, fm, "/attendance-sheets", {"project_id": ctx["project"]["id"], "work_date": str(T), "entries": [
        {"worker_id": ws[0]["id"], "status": "PRESENT"}, {"worker_id": ws[1]["id"], "status": "HALF_DAY"},
        {"worker_id": ws[2]["id"], "status": "ABSENT"}]}, 201)
    log = mk_log(client, eng, ctx, T)
    assert log["workforce"]["attendance_recorded"] is False       # draft attendance is not reported yet
    sh = client.get("/attendance-sheets", headers=fm).json()[0]
    post(client, fm, f"/attendance-sheets/{sh['id']}/submit")
    post(client, h, "/inventory/adjustments", {"warehouse_id": ctx["wh"]["id"], "item_id": ctx["item"]["id"],
                                               "kind": "OPENING_STOCK", "quantity": "100", "unit_cost": "1300",
                                               "reason": "opening balance"}, 201)
    post(client, eng, "/inventory/issues", {"warehouse_id": ctx["wh"]["id"], "project_id": ctx["project"]["id"],
                                            "lines": [{"item_id": ctx["item"]["id"], "quantity": "20"}]}, 201)
    got = client.get(f"/daily-logs/{log['id']}", headers=eng).json()
    wf = got["workforce"]
    assert (wf["attendance_recorded"], wf["present"], wf["half_day"], wf["absent"], wf["workers_on_site"]) == (True, 1, 1, 1, 2)
    assert got["materials"]["issued"] == [{"item_code": "CEMENT", "item_name": "Cement 50kg", "quantity": "20.0000"}]
    assert got["materials"]["received"] == []


def test_lifecycle_locking_and_reopen(client):
    ctx = bootstrap(client)
    eng, pm = ctx["u"]["SITE_ENGINEER"], ctx["u"]["PROJECT_MANAGER"]
    empty = post(client, eng, "/daily-logs", {"project_id": ctx["project"]["id"], "log_date": str(T - timedelta(days=5))}, 201)
    assert client.post(f"/daily-logs/{empty['id']}/submit", headers=eng).status_code == 422     # nothing reported
    log = mk_log(client, eng, ctx, T)
    assert client.post("/daily-logs", headers=eng, json={"project_id": ctx["project"]["id"], "log_date": str(T)}).status_code == 409
    post(client, eng, f"/daily-logs/{log['id']}/submit")
    body = {"work_completed": "edited", "progress": []}
    assert client.put(f"/daily-logs/{log['id']}", headers=eng, json=body).status_code == 409    # locked
    assert client.post(f"/daily-logs/{log['id']}/reopen", headers=eng, json={"reason": "typo"}).status_code == 403
    assert client.post(f"/daily-logs/{log['id']}/reopen", headers=pm, json={"reason": ""}).status_code == 422
    post(client, pm, f"/daily-logs/{log['id']}/reopen", {"reason": "Wrong quantity entered"})
    r = client.put(f"/daily-logs/{log['id']}", headers=eng, json=body)
    assert r.status_code == 200 and r.json()["work_completed"] == "edited"
    assert "dailylog.reopen" in {e["action"] for e in client.get("/audit-logs?limit=300", headers=ctx["h"]).json()}


def test_progress_validation_and_cross_tenant_boq_item(client):
    ctx = bootstrap(client)
    other = bootstrap(client, "Beta", "b@beta.pk")
    eng = ctx["u"]["SITE_ENGINEER"]
    bad = lambda progress: client.post("/daily-logs", headers=eng, json={  # noqa: E731
        "project_id": ctx["project"]["id"], "log_date": str(T), "work_completed": "x", "progress": progress})
    assert bad([{"boq_item_id": other["boq_item"]["id"], "quantity": "1"}]).status_code == 422
    assert bad(prog(ctx, "0")).status_code == 422
    assert bad(prog(ctx, "5") + prog(ctx, "6")).status_code == 422
    assert client.get("/daily-logs", headers=eng).json() == []             # failed creates left no rows
    ok = mk_log(client, eng, ctx, T, prog(ctx, "5"))
    assert ok["status"] == "DRAFT"


def test_missing_reports_and_rbac(client):
    ctx = bootstrap(client)
    eng, store, h = ctx["u"]["SITE_ENGINEER"], ctx["u"]["STOREKEEPER"], ctx["h"]
    d0, d1, d2 = T - timedelta(days=2), T - timedelta(days=1), T
    l = mk_log(client, eng, ctx, d1)
    post(client, eng, f"/daily-logs/{l['id']}/submit")
    mk_log(client, eng, ctx, d2)                                           # draft only: still "missing"
    miss = client.get("/daily-logs/missing", headers=h, params={"project_id": ctx["project"]["id"],
                                                                "date_from": str(d0), "date_to": str(d2)}).json()
    assert miss["missing"] == [str(d0), str(d2)]
    assert client.get("/daily-logs/missing", headers=h, params={"project_id": ctx["project"]["id"], "date_from": "2026-01-01",
                                                                "date_to": "2026-12-31"}).status_code == 422
    assert client.get("/daily-logs", headers=store).status_code == 403
    assert client.post("/daily-logs", headers=store, json={"project_id": ctx["project"]["id"], "log_date": str(T)}).status_code == 403
    fm = add_user(client, h, "fm@alpha.pk", "FOREMAN")
    assert client.get("/daily-logs", headers=fm).status_code == 200


def test_pdf_export_content_and_isolation(client):
    ctx = bootstrap(client, "Alpha Builders", "a@alpha.pk")
    eng = ctx["u"]["SITE_ENGINEER"]
    log = mk_log(client, eng, ctx, T, prog(ctx, "650"), issues="Rain delayed shuttering <2h> & cement shortage",
                 tomorrow_plan="Pour slab B")
    post(client, eng, f"/daily-logs/{log['id']}/submit")
    r = client.get(f"/daily-logs/{log['id']}/pdf", headers=ctx["h"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    assert f"daily-report-ABC-01-{T}.pdf" in r.headers["content-disposition"]
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(r.content)).pages)
    for needle in ("Alpha Builders", "Daily Site Report", "ABC-01 - ABC Plaza", str(T), "Columns cast on grid A-C",
                   "Rain delayed shuttering <2h> & cement shortage", "Pour slab B", "CEM", "65.00"):
        assert needle in text, needle                                       # incl. special characters, escaped safely
    hb = register(client, "Beta", "b@beta.pk")
    assert client.get(f"/daily-logs/{log['id']}/pdf", headers=hb).status_code == 404
    assert client.get(f"/daily-logs/{log['id']}", headers=hb).status_code == 404
    assert client.get(f"/projects/{ctx['project']['id']}/progress", headers=hb).status_code == 404
