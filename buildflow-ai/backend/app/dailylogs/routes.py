import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.boq import calculations as calc
from app.boq.models import BOQ, ApprovalStatus, BOQItem
from app.dailylogs import service
from app.dailylogs.models import DailyLog, DailyLogProgress, LogStatus
from app.dailylogs.pdf import build_pdf
from app.dailylogs.schemas import LogBody, LogCreate, LogOut, ProgressOut, ReopenIn
from app.db import get_db
from app.deps import get_owned, org_scoped, require_permission
from app.models import Organization, User
from app.projects.models import Project, Site

router = APIRouter(tags=["daily-logs"])
READ = require_permission("dailylog.read")
SUBMIT = require_permission("dailylog.submit")
REOPEN = require_permission("dailylog.approve")


def _out(db: Session, log: DailyLog) -> LogOut:
    cum = service.cumulative_by_item(db, log.organization_id, log.project_id, log.log_date)
    rows = []
    for pr in db.scalars(select(DailyLogProgress).where(DailyLogProgress.log_id == log.id)):
        bi = db.get(BOQItem, pr.boq_item_id)
        # a draft's own quantity is not in the submitted cumulative yet: show what it would become
        total = cum.get(bi.id, 0) + (pr.quantity if log.status == LogStatus.DRAFT else 0)
        rows.append(ProgressOut(boq_item_id=bi.id, item_code=bi.item_code, description=bi.description,
                                quantity_today=pr.quantity, cumulative=total, boq_quantity=bi.quantity,
                                percent=service.pct(total, bi.quantity), notes=pr.notes))
    rows.sort(key=lambda r: r.item_code)
    return LogOut(id=log.id, project_id=log.project_id, site_id=log.site_id, log_date=log.log_date, status=log.status,
                  weather=log.weather, work_completed=log.work_completed, equipment=log.equipment, issues=log.issues,
                  safety=log.safety, quality=log.quality, tomorrow_plan=log.tomorrow_plan, progress=rows,
                  workforce=service.workforce(db, log.organization_id, log.project_id, log.log_date),
                  materials=service.materials(db, log.organization_id, log.project_id, log.log_date))


def _apply(db, user, log: DailyLog, body: LogBody):
    if body.site_id:
        site = get_owned(db, Site, body.site_id, user, code=422)
        if site.project_id != log.project_id:
            raise HTTPException(422, "Site belongs to a different project")
    ids = [p.boq_item_id for p in body.progress]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Each BOQ item can appear once per report")
    for pr in body.progress:
        bi = get_owned(db, BOQItem, pr.boq_item_id, user, code=422)
        boq = db.get(BOQ, bi.boq_id)
        if boq.project_id != log.project_id or boq.status != ApprovalStatus.APPROVED:
            raise HTTPException(422, f"BOQ item {bi.item_code} is not in an approved BOQ of this project")
    for f in ("site_id", "weather", "work_completed", "equipment", "issues", "safety", "quality", "tomorrow_plan"):
        setattr(log, f, getattr(body, f))
    for old in db.scalars(select(DailyLogProgress).where(DailyLogProgress.log_id == log.id)):
        db.delete(old)
    db.flush()
    for pr in body.progress:
        db.add(DailyLogProgress(organization_id=user.organization_id, log_id=log.id, **pr.model_dump()))


@router.post("/daily-logs", response_model=LogOut, status_code=201)
def create_log(body: LogCreate, request: Request, user: User = Depends(SUBMIT), db: Session = Depends(get_db)):
    project = get_owned(db, Project, body.project_id, user, code=422)
    if db.scalar(org_scoped(DailyLog, user).where(DailyLog.project_id == project.id, DailyLog.log_date == body.log_date)):
        raise HTTPException(409, "A daily report already exists for this project and date")
    log = DailyLog(organization_id=user.organization_id, project_id=project.id, log_date=body.log_date, created_by=user.id)
    db.add(log)
    try:
        db.flush()
        _apply(db, user, log, body)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A daily report already exists for this project and date")
    log_action(db, action="dailylog.create", org_id=user.organization_id, user_id=user.id, entity="daily_log",
               entity_id=log.id, request=request)
    return _out(db, log)


@router.put("/daily-logs/{log_id}", response_model=LogOut)
def update_log(log_id: uuid.UUID, body: LogBody, request: Request, user: User = Depends(SUBMIT),
               db: Session = Depends(get_db)):
    log = get_owned(db, DailyLog, log_id, user)
    if log.status != LogStatus.DRAFT:
        raise HTTPException(409, "Submitted reports are locked; ask a manager to reopen it")
    try:
        _apply(db, user, log, body)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    log_action(db, action="dailylog.update", org_id=user.organization_id, user_id=user.id, entity="daily_log",
               entity_id=log.id, request=request)
    return _out(db, log)


@router.post("/daily-logs/{log_id}/submit", response_model=LogOut)
def submit_log(log_id: uuid.UUID, request: Request, user: User = Depends(SUBMIT), db: Session = Depends(get_db)):
    log = get_owned(db, DailyLog, log_id, user)
    if log.status != LogStatus.DRAFT:
        raise HTTPException(409, "Report is already submitted")
    if not log.work_completed.strip() and not db.scalar(select(DailyLogProgress.id).where(DailyLogProgress.log_id == log.id).limit(1)):
        raise HTTPException(422, "Describe the work completed or record quantities before submitting")
    log.status, log.submitted_by, log.submitted_at = LogStatus.SUBMITTED, user.id, datetime.now(timezone.utc)
    db.commit()
    log_action(db, action="dailylog.submit", org_id=user.organization_id, user_id=user.id, entity="daily_log",
               entity_id=log.id, request=request)
    return _out(db, log)


@router.post("/daily-logs/{log_id}/reopen", response_model=LogOut)
def reopen_log(log_id: uuid.UUID, body: ReopenIn, request: Request, user: User = Depends(REOPEN),
               db: Session = Depends(get_db)):
    log = get_owned(db, DailyLog, log_id, user)
    if log.status != LogStatus.SUBMITTED:
        raise HTTPException(409, "Only submitted reports can be reopened")
    log.status = LogStatus.DRAFT
    db.commit()
    log_action(db, action="dailylog.reopen", org_id=user.organization_id, user_id=user.id, entity="daily_log",
               entity_id=log.id, request=request, detail={"reason": body.reason})
    return _out(db, log)


@router.get("/daily-logs/missing")
def missing_logs(project_id: uuid.UUID, date_from: date, date_to: date, user: User = Depends(READ),
                 db: Session = Depends(get_db)):
    get_owned(db, Project, project_id, user)
    if date_to < date_from or (date_to - date_from).days > 62:
        raise HTTPException(422, "Range must be 0-62 days")
    have = set(db.scalars(org_scoped(DailyLog, user).with_only_columns(DailyLog.log_date).where(
        DailyLog.project_id == project_id, DailyLog.status == LogStatus.SUBMITTED,
        DailyLog.log_date.between(date_from, date_to))))
    days = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
    return {"project_id": str(project_id), "missing": [str(d) for d in days if d not in have]}


@router.get("/daily-logs", response_model=list[LogOut])
def list_logs(project_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None,
              status: LogStatus | None = None, limit: int = 50, user: User = Depends(READ), db: Session = Depends(get_db)):
    q = org_scoped(DailyLog, user)
    if project_id:
        q = q.where(DailyLog.project_id == project_id)
    if date_from:
        q = q.where(DailyLog.log_date >= date_from)
    if date_to:
        q = q.where(DailyLog.log_date <= date_to)
    if status:
        q = q.where(DailyLog.status == status)
    return [_out(db, l) for l in db.scalars(q.order_by(DailyLog.log_date.desc()).limit(min(limit, 100)))]


@router.get("/daily-logs/{log_id}", response_model=LogOut)
def get_log(log_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    return _out(db, get_owned(db, DailyLog, log_id, user))


@router.get("/daily-logs/{log_id}/pdf")
def log_pdf(log_id: uuid.UUID, request: Request, user: User = Depends(READ), db: Session = Depends(get_db)):
    log = get_owned(db, DailyLog, log_id, user)
    project = db.get(Project, log.project_id)
    org = db.get(Organization, user.organization_id)
    pdf = build_pdf(org_name=org.name, project={"code": project.code, "name": project.name},
                    log=_out(db, log).model_dump(mode="json"))
    log_action(db, action="dailylog.pdf", org_id=user.organization_id, user_id=user.id, entity="daily_log",
               entity_id=log.id, request=request)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="daily-report-{project.code}-{log.log_date}.pdf"'})


@router.get("/projects/{project_id}/progress")
def progress(project_id: uuid.UUID, as_of: date | None = None, user: User = Depends(READ), db: Session = Depends(get_db)):
    get_owned(db, Project, project_id, user)
    return service.project_progress(db, user.organization_id, project_id, as_of)
