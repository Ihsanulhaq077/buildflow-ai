"""Derived report sections and quantity-based progress (all deterministic Decimal)."""
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.boq import calculations as calc
from app.boq.models import BOQ, ApprovalStatus, BOQItem
from app.dailylogs.models import DailyLog, DailyLogProgress, LogStatus
from app.inventory.models import InventoryItem, StockTransaction
from app.inventory.models import MovementType as MT
from app.labour.models import AttendanceEntry, AttendanceSheet, AttendanceStatus, SheetStatus
from app.timeutil import day_bounds_utc

HUNDRED = Decimal("100")


def pct(done: Decimal, total: Decimal) -> Decimal:
    return calc.q2(done / total * HUNDRED) if total else Decimal("0.00")


def cumulative_by_item(db: Session, org_id, project_id, up_to: date | None = None) -> dict[uuid.UUID, Decimal]:
    q = (select(DailyLogProgress.boq_item_id, DailyLogProgress.quantity)
         .join(DailyLog, DailyLog.id == DailyLogProgress.log_id)
         .where(DailyLog.organization_id == org_id, DailyLog.project_id == project_id,
                DailyLog.status == LogStatus.SUBMITTED))
    if up_to:
        q = q.where(DailyLog.log_date <= up_to)
    out: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for item_id, qty in db.execute(q):
        out[item_id] += qty
    return out


def project_progress(db: Session, org_id, project_id, up_to: date | None = None) -> dict:
    """Per-item % = completed / BOQ quantity. Overall % is weighted by item amount, each item capped at 100%."""
    items = list(db.scalars(select(BOQItem).join(BOQ, BOQ.id == BOQItem.boq_id)
                            .where(BOQItem.organization_id == org_id, BOQ.project_id == project_id,
                                   BOQ.status == ApprovalStatus.APPROVED).order_by(BOQItem.item_code)))
    done = cumulative_by_item(db, org_id, project_id, up_to)
    rows, w_done, w_total = [], Decimal("0"), Decimal("0")
    for i in items:
        amount = calc.item_amount(i.quantity, calc.unit_rate(i.material_rate, i.waste_pct, i.labour_rate, i.equipment_rate))
        completed = done.get(i.id, Decimal("0"))
        w_total += amount
        w_done += amount * min(completed / i.quantity, Decimal("1"))
        rows.append({"boq_item_id": str(i.id), "item_code": i.item_code, "description": i.description,
                     "boq_quantity": str(i.quantity), "completed": str(completed), "percent": str(pct(completed, i.quantity)),
                     "amount": str(amount)})
    return {"project_id": str(project_id), "as_of": str(up_to) if up_to else None,
            "overall_percent": str(pct(w_done, w_total)), "items": rows}


def workforce(db: Session, org_id, project_id, d: date) -> dict:
    sheets = list(db.scalars(select(AttendanceSheet).where(
        AttendanceSheet.organization_id == org_id, AttendanceSheet.project_id == project_id,
        AttendanceSheet.work_date == d, AttendanceSheet.status.in_([SheetStatus.SUBMITTED, SheetStatus.APPROVED]))))
    counts = {s.value: 0 for s in AttendanceStatus}
    ot = Decimal("0")
    for sh in sheets:
        for e in db.scalars(select(AttendanceEntry).where(AttendanceEntry.sheet_id == sh.id)):
            counts[e.status.value] += 1
            ot += e.overtime_hours
    return {"attendance_recorded": bool(sheets), "present": counts["PRESENT"], "half_day": counts["HALF_DAY"],
            "absent": counts["ABSENT"], "leave": counts["LEAVE"], "overtime_hours": str(ot),
            "workers_on_site": counts["PRESENT"] + counts["HALF_DAY"]}


def materials(db: Session, org_id, project_id, d: date) -> dict:
    start, end = day_bounds_utc(d)
    q = select(StockTransaction).where(
        StockTransaction.organization_id == org_id, StockTransaction.project_id == project_id,
        StockTransaction.created_at >= start, StockTransaction.created_at < end,
        StockTransaction.type.in_([MT.PURCHASE_RECEIPT, MT.MATERIAL_ISSUE, MT.MATERIAL_RETURN]))
    items = {i.id: i for i in db.scalars(select(InventoryItem).where(InventoryItem.organization_id == org_id))}
    agg: dict[str, dict[uuid.UUID, Decimal]] = {"received": defaultdict(lambda: Decimal("0")),
                                                "issued": defaultdict(lambda: Decimal("0")),
                                                "returned": defaultdict(lambda: Decimal("0"))}
    for t in db.scalars(q):
        key = {MT.PURCHASE_RECEIPT: "received", MT.MATERIAL_ISSUE: "issued", MT.MATERIAL_RETURN: "returned"}[t.type]
        agg[key][t.item_id] += abs(t.quantity)
    return {k: [{"item_code": items[i].code, "item_name": items[i].name, "quantity": str(q)}
                for i, q in sorted(v.items(), key=lambda kv: items[kv[0]].code)] for k, v in agg.items()}
