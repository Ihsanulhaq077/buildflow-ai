"""Workers, attendance sheets (draft -> submitted -> approved) and labour cost.
Approving a sheet posts labour cost to the budget as committed + actual together (no PO stage for labour)."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.boq.models import CostCategory, CostCode
from app.budgets import service as budget_service
from app.db import get_db
from app.deps import get_current_user, get_owned, org_scoped, require_permission
from app.labour import calculations as calc
from app.labour.models import DAYS, AttendanceEntry, AttendanceSheet, AttendanceStatus, SheetStatus, Worker
from app.labour.schemas import (EntriesIn, EntryIn, EntryOut, RejectIn, SheetIn, SheetOut, WorkerIn, WorkerOut,
                                WorkerUpdate)
from app.models import User
from app.projects.models import Project

router = APIRouter(tags=["labour"])
MANAGE = require_permission("workers.manage")
SUBMIT = require_permission("attendance.submit")
APPROVE = require_permission("attendance.approve")
COST_PERM = "labour.read"


def _perms(user: User) -> set[str]:
    return {p.code for p in user.role.permissions}


def _can_read_attendance(user: User = Depends(get_current_user)) -> User:
    if not _perms(user) & {"attendance.read", "workers.manage", "attendance.submit"}:
        raise HTTPException(403, "Permission denied")
    return user


def _need_cost(user: User = Depends(get_current_user)) -> User:
    if COST_PERM not in _perms(user):
        raise HTTPException(403, "Permission denied")
    return user


# ---- workers
def _worker_out(w: Worker, user: User) -> WorkerOut:
    out = WorkerOut.model_validate(w)          # copies every matching attribute, including rates...
    if COST_PERM not in _perms(user):
        out.daily_rate = out.overtime_rate = None   # ...so pay data is explicitly stripped without labour.read
    return out


def _check_labour_code(db, user, cost_code_id):
    if cost_code_id:
        cc = get_owned(db, CostCode, cost_code_id, user, code=422)
        if cc.category != CostCategory.LABOUR:
            raise HTTPException(422, "Labour must be charged to a LABOUR cost code")


@router.post("/workers", response_model=WorkerOut, status_code=201)
def create_worker(body: WorkerIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    _check_labour_code(db, user, body.cost_code_id)
    if db.scalar(org_scoped(Worker, user).where(Worker.code == body.code)):
        raise HTTPException(409, "Worker code already exists")
    w = Worker(organization_id=user.organization_id, **body.model_dump())
    db.add(w)
    db.commit()
    log_action(db, action="worker.create", org_id=user.organization_id, user_id=user.id, entity="worker",
               entity_id=w.id, request=request)
    return _worker_out(w, user)


@router.get("/workers", response_model=list[WorkerOut])
def list_workers(active: bool | None = None, trade: str | None = None, limit: int = 500,
                 user: User = Depends(_can_read_attendance), db: Session = Depends(get_db)):
    q = org_scoped(Worker, user)
    if active is not None:
        q = q.where(Worker.is_active == active)
    if trade:
        q = q.where(Worker.trade == trade)
    return [_worker_out(w, user) for w in db.scalars(q.order_by(Worker.code).limit(min(limit, 1000)))]


@router.patch("/workers/{worker_id}", response_model=WorkerOut)
def update_worker(worker_id: uuid.UUID, body: WorkerUpdate, request: Request, user: User = Depends(MANAGE),
                  db: Session = Depends(get_db)):
    w = get_owned(db, Worker, worker_id, user)
    data = body.model_dump(exclude_unset=True)
    _check_labour_code(db, user, data.get("cost_code_id"))
    for k, v in data.items():
        if v is not None or k == "cost_code_id":
            setattr(w, k, v)
    db.commit()
    log_action(db, action="worker.update", org_id=user.organization_id, user_id=user.id, entity="worker",
               entity_id=w.id, request=request, detail={"fields": list(data)})  # rate changes are auditable
    return _worker_out(w, user)


# ---- attendance sheets
def _entries(db, sheet) -> list[AttendanceEntry]:
    return list(db.scalars(select(AttendanceEntry).where(AttendanceEntry.sheet_id == sheet.id,
                                                         AttendanceEntry.organization_id == sheet.organization_id)))


def _sheet_out(db, sheet: AttendanceSheet, user: User) -> SheetOut:
    show = COST_PERM in _perms(user)
    ents = _entries(db, sheet)
    workers = {w.id: w for w in db.scalars(org_scoped(Worker, user).where(Worker.id.in_([e.worker_id for e in ents] or [None])))}
    ents.sort(key=lambda e: workers[e.worker_id].code)
    count = lambda st: sum(1 for e in ents if e.status == st)  # noqa: E731
    return SheetOut(
        id=sheet.id, project_id=sheet.project_id, work_date=sheet.work_date, status=sheet.status,
        decision_comment=sheet.decision_comment, present=count(AttendanceStatus.PRESENT),
        half_day=count(AttendanceStatus.HALF_DAY), absent=count(AttendanceStatus.ABSENT),
        leave=count(AttendanceStatus.LEAVE), total_days=sum((e.days for e in ents), Decimal("0")),
        total_overtime_hours=sum((e.overtime_hours for e in ents), Decimal("0")),
        total_cost=sum((e.cost for e in ents), Decimal("0")) if show else None,
        entries=[EntryOut(worker_id=e.worker_id, worker_code=workers[e.worker_id].code,
                          worker_name=workers[e.worker_id].name, status=e.status, days=e.days,
                          overtime_hours=e.overtime_hours, cost_code_id=e.cost_code_id,
                          cost=e.cost if show else None) for e in ents])


def _replace_entries(db, user, sheet: AttendanceSheet, entries: list[EntryIn]):
    ids = [e.worker_id for e in entries]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "A worker can appear only once per sheet")
    for old in _entries(db, sheet):
        db.delete(old)
    db.flush()
    for e in entries:
        w = get_owned(db, Worker, e.worker_id, user, code=422)
        if not w.is_active:
            raise HTTPException(422, f"Worker {w.code} is inactive")
        days = DAYS[e.status]
        if e.overtime_hours > 0 and days == 0:
            raise HTTPException(422, f"Worker {w.code}: overtime requires PRESENT or HALF_DAY")
        if e.overtime_hours > 0 and w.overtime_rate <= 0:
            raise HTTPException(422, f"Worker {w.code} has no overtime rate configured")
        _check_labour_code(db, user, e.cost_code_id)
        booked = db.scalar(select(func.coalesce(func.sum(AttendanceEntry.days), 0))
                           .join(AttendanceSheet, AttendanceSheet.id == AttendanceEntry.sheet_id)
                           .where(AttendanceEntry.organization_id == user.organization_id,
                                  AttendanceEntry.worker_id == w.id, AttendanceSheet.work_date == sheet.work_date,
                                  AttendanceSheet.id != sheet.id))
        if Decimal(booked) + days > 1:
            raise HTTPException(409, f"Worker {w.code} is already booked for {sheet.work_date} on another sheet")
        db.add(AttendanceEntry(
            organization_id=user.organization_id, sheet_id=sheet.id, worker_id=w.id, status=e.status,
            overtime_hours=e.overtime_hours, cost_code_id=e.cost_code_id or w.cost_code_id, days=days,
            daily_rate=w.daily_rate, overtime_rate=w.overtime_rate,
            cost=calc.entry_cost(e.status, e.overtime_hours, w.daily_rate, w.overtime_rate)))
    db.flush()


@router.post("/attendance-sheets", response_model=SheetOut, status_code=201)
def create_sheet(body: SheetIn, request: Request, user: User = Depends(SUBMIT), db: Session = Depends(get_db)):
    project = get_owned(db, Project, body.project_id, user, code=422)
    if db.scalar(org_scoped(AttendanceSheet, user).where(AttendanceSheet.project_id == project.id,
                                                         AttendanceSheet.work_date == body.work_date)):
        raise HTTPException(409, "An attendance sheet already exists for this project and date")
    sheet = AttendanceSheet(organization_id=user.organization_id, project_id=project.id, work_date=body.work_date,
                            created_by=user.id)
    db.add(sheet)
    try:
        db.flush()
        _replace_entries(db, user, sheet, body.entries)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An attendance sheet already exists for this project and date")
    log_action(db, action="attendance.create", org_id=user.organization_id, user_id=user.id,
               entity="attendance_sheet", entity_id=sheet.id, request=request)
    return _sheet_out(db, sheet, user)


@router.put("/attendance-sheets/{sheet_id}/entries", response_model=SheetOut)
def replace_entries(sheet_id: uuid.UUID, body: EntriesIn, request: Request, user: User = Depends(SUBMIT),
                    db: Session = Depends(get_db)):
    sheet = get_owned(db, AttendanceSheet, sheet_id, user)
    if sheet.status != SheetStatus.DRAFT:
        raise HTTPException(409, f"Sheet is {sheet.status.value}; only DRAFT sheets can be edited")
    try:
        _replace_entries(db, user, sheet, body.entries)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    log_action(db, action="attendance.update", org_id=user.organization_id, user_id=user.id,
               entity="attendance_sheet", entity_id=sheet.id, request=request)
    return _sheet_out(db, sheet, user)


@router.get("/attendance-sheets", response_model=list[SheetOut])
def list_sheets(project_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None,
                status: SheetStatus | None = None, limit: int = 100, user: User = Depends(_can_read_attendance),
                db: Session = Depends(get_db)):
    q = org_scoped(AttendanceSheet, user)
    if project_id:
        q = q.where(AttendanceSheet.project_id == project_id)
    if date_from:
        q = q.where(AttendanceSheet.work_date >= date_from)
    if date_to:
        q = q.where(AttendanceSheet.work_date <= date_to)
    if status:
        q = q.where(AttendanceSheet.status == status)
    return [_sheet_out(db, s, user) for s in db.scalars(q.order_by(AttendanceSheet.work_date.desc()).limit(min(limit, 200)))]


@router.get("/attendance-sheets/{sheet_id}", response_model=SheetOut)
def get_sheet(sheet_id: uuid.UUID, user: User = Depends(_can_read_attendance), db: Session = Depends(get_db)):
    return _sheet_out(db, get_owned(db, AttendanceSheet, sheet_id, user), user)


@router.post("/attendance-sheets/{sheet_id}/submit", response_model=SheetOut)
def submit_sheet(sheet_id: uuid.UUID, request: Request, user: User = Depends(SUBMIT), db: Session = Depends(get_db)):
    sheet = get_owned(db, AttendanceSheet, sheet_id, user)
    if sheet.status != SheetStatus.DRAFT:
        raise HTTPException(409, f"Sheet is {sheet.status.value}")
    if not _entries(db, sheet):
        raise HTTPException(422, "Cannot submit an empty sheet")
    sheet.status, sheet.submitted_by, sheet.decision_comment = SheetStatus.SUBMITTED, user.id, ""
    db.commit()
    log_action(db, action="attendance.submit", org_id=user.organization_id, user_id=user.id,
               entity="attendance_sheet", entity_id=sheet.id, request=request)
    return _sheet_out(db, sheet, user)


@router.post("/attendance-sheets/{sheet_id}/approve", response_model=SheetOut)
def approve_sheet(sheet_id: uuid.UUID, request: Request, user: User = Depends(APPROVE), db: Session = Depends(get_db)):
    sheet = get_owned(db, AttendanceSheet, sheet_id, user)
    if sheet.status != SheetStatus.SUBMITTED:
        raise HTTPException(409, f"Sheet is {sheet.status.value}; expected SUBMITTED")
    ents = _entries(db, sheet)
    missing = [e.worker_id for e in ents if e.cost > 0 and not e.cost_code_id]
    if missing:
        raise HTTPException(422, "Entries with pay need a LABOUR cost code (set it on the entry or on the worker)")
    try:
        budget_service.record_direct_cost(db, user.organization_id, sheet.project_id,
                                     budget_service.group((e.cost_code_id, e.cost) for e in ents if e.cost > 0))
    except HTTPException:
        db.rollback()
        raise
    sheet.status, sheet.approved_by, sheet.approved_at = SheetStatus.APPROVED, user.id, datetime.now(timezone.utc)
    db.commit()
    log_action(db, action="attendance.approve", org_id=user.organization_id, user_id=user.id,
               entity="attendance_sheet", entity_id=sheet.id, request=request,
               detail={"total_cost": str(sum((e.cost for e in ents), Decimal("0")))})
    return _sheet_out(db, sheet, user)


@router.post("/attendance-sheets/{sheet_id}/reject", response_model=SheetOut)
def reject_sheet(sheet_id: uuid.UUID, body: RejectIn, request: Request, user: User = Depends(APPROVE),
                 db: Session = Depends(get_db)):
    sheet = get_owned(db, AttendanceSheet, sheet_id, user)
    if sheet.status != SheetStatus.SUBMITTED:
        raise HTTPException(409, f"Sheet is {sheet.status.value}; expected SUBMITTED")
    sheet.status, sheet.decision_comment = SheetStatus.DRAFT, body.comment
    db.commit()
    log_action(db, action="attendance.reject", org_id=user.organization_id, user_id=user.id,
               entity="attendance_sheet", entity_id=sheet.id, request=request, detail={"comment": body.comment})
    return _sheet_out(db, sheet, user)


# ---- labour cost (approved sheets only)
@router.get("/labour/cost-summary")
def cost_summary(project_id: uuid.UUID, date_from: date | None = None, date_to: date | None = None,
                 user: User = Depends(_need_cost), db: Session = Depends(get_db)):
    get_owned(db, Project, project_id, user)
    q = (select(AttendanceEntry, AttendanceSheet.work_date)
         .join(AttendanceSheet, AttendanceSheet.id == AttendanceEntry.sheet_id)
         .where(AttendanceEntry.organization_id == user.organization_id, AttendanceSheet.project_id == project_id,
                AttendanceSheet.status == SheetStatus.APPROVED))
    if date_from:
        q = q.where(AttendanceSheet.work_date >= date_from)
    if date_to:
        q = q.where(AttendanceSheet.work_date <= date_to)
    workers = {w.id: w for w in db.scalars(org_scoped(Worker, user))}
    codes = {c.id: c for c in db.scalars(org_scoped(CostCode, user))}
    by_worker: dict = {}
    by_code: dict = {}
    total = Decimal("0")
    for e, _d in db.execute(q):
        w = by_worker.setdefault(e.worker_id, {"worker_id": str(e.worker_id), "worker_code": workers[e.worker_id].code,
                                               "worker_name": workers[e.worker_id].name, "days": Decimal("0"),
                                               "overtime_hours": Decimal("0"), "amount": Decimal("0")})
        w["days"] += e.days
        w["overtime_hours"] += e.overtime_hours
        w["amount"] += e.cost
        c = by_code.setdefault(e.cost_code_id, {"cost_code_id": str(e.cost_code_id) if e.cost_code_id else None,
                                                "code": codes[e.cost_code_id].code if e.cost_code_id else None,
                                                "amount": Decimal("0")})
        c["amount"] += e.cost
        total += e.cost
    fmt = lambda rows: [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()}  # noqa: E731
                        for r in sorted(rows, key=lambda r: r.get("worker_code") or r.get("code") or "")]
    return {"project_id": str(project_id), "total": str(total), "by_cost_code": fmt(by_code.values()),
            "by_worker": fmt(by_worker.values())}
