import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.boq import calculations as calc
from app.boq.models import BOQ, ApprovalStatus, BOQItem, CostCategory, CostCode
from app.budgets.models import Budget, BudgetLine, BudgetRevision
from app.budgets.schemas import BudgetOut, FromBOQ, LineIn, LineOut, LineUpdate, Revise, RevisionOut, Totals
from app.db import get_db
from app.deps import get_owned, org_scoped, require_permission
from app.models import User
from app.projects.models import Project

router = APIRouter(tags=["budgets"])
READ = require_permission("budgets.read")
MANAGE = require_permission("budgets.manage")
APPROVE = require_permission("budgets.approve")
ZERO = Decimal("0")


def _lines(db: Session, budget: Budget) -> list[BudgetLine]:
    return list(db.scalars(select(BudgetLine).where(BudgetLine.budget_id == budget.id,
                                                    BudgetLine.organization_id == budget.organization_id)
                           .order_by(BudgetLine.created_at, BudgetLine.description)))


def _out(db: Session, budget: Budget) -> BudgetOut:
    lines = _lines(db, budget)
    project = db.get(Project, budget.project_id)
    s = lambda attr: sum((getattr(l, attr) for l in lines), ZERO)  # noqa: E731
    revised, committed, actual = s("revised_amount"), s("committed_amount"), s("actual_amount")
    cv = project.contract_value
    margin = cv - revised
    by_cat: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for l in lines:
        by_cat[l.category.value] += l.revised_amount
    totals = Totals(original=s("original_amount"), revised=revised, committed=committed, actual=actual,
                    paid=s("paid_amount"), remaining=revised - committed, variance=revised - actual,
                    contract_value=cv, planned_margin=margin,
                    planned_margin_pct=calc.q2(margin / cv * 100) if cv else Decimal("0.00"),
                    by_category=dict(by_cat))
    return BudgetOut(id=budget.id, project_id=budget.project_id, boq_id=budget.boq_id, status=budget.status,
                     lines=[LineOut.model_validate(l) for l in lines], totals=totals)


def _draft(budget: Budget):
    if budget.status != ApprovalStatus.DRAFT:
        raise HTTPException(409, "Approved budgets can only change through revisions")


@router.post("/budgets/from-boq", response_model=BudgetOut, status_code=201)
def create_from_boq(body: FromBOQ, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    boq = get_owned(db, BOQ, body.boq_id, user, code=422)
    if boq.status != ApprovalStatus.APPROVED:
        raise HTTPException(409, "BOQ must be approved before creating a budget")
    if db.scalar(org_scoped(Budget, user).where(Budget.project_id == boq.project_id)):
        raise HTTPException(409, "This project already has a budget")
    items = list(db.scalars(select(BOQItem).where(BOQItem.boq_id == boq.id)))
    missing = sorted(i.item_code for i in items if not i.cost_code_id)
    if missing:
        raise HTTPException(422, f"BOQ items without a cost code: {', '.join(missing)}")
    codes = {c.id: c for c in db.scalars(org_scoped(CostCode, user))}
    per_code: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for i in items:
        rate = calc.unit_rate(i.material_rate, i.waste_pct, i.labour_rate, i.equipment_rate)
        per_code[i.cost_code_id] += calc.item_amount(i.quantity, rate)
    summary = calc.summarize(items, boq.overhead_pct, boq.contingency_pct, boq.profit_pct)

    budget = Budget(organization_id=user.organization_id, project_id=boq.project_id, boq_id=boq.id,
                    created_by=user.id)
    db.add(budget)
    db.flush()

    def add(category, cost_code_id, desc, amount):
        db.add(BudgetLine(organization_id=user.organization_id, budget_id=budget.id, category=category,
                          cost_code_id=cost_code_id, description=desc, original_amount=amount,
                          revised_amount=amount))

    for cid, amount in sorted(per_code.items(), key=lambda kv: codes[kv[0]].code):
        add(codes[cid].category, cid, f"{codes[cid].code} - {codes[cid].name}", amount)
    if summary["overhead"] > 0:
        add(CostCategory.OVERHEAD, None, "Overhead (from BOQ)", summary["overhead"])
    if summary["contingency"] > 0:
        add(CostCategory.CONTINGENCY, None, "Contingency (from BOQ)", summary["contingency"])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This project already has a budget")
    log_action(db, action="budget.create", org_id=user.organization_id, user_id=user.id, entity="budget",
               entity_id=budget.id, request=request, detail={"boq": str(boq.id)})
    return _out(db, budget)


@router.get("/projects/{project_id}/budget", response_model=BudgetOut)
def project_budget(project_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    project = get_owned(db, Project, project_id, user)
    budget = db.scalar(org_scoped(Budget, user).where(Budget.project_id == project.id))
    if not budget:
        raise HTTPException(404, "Budget not found")
    return _out(db, budget)


@router.post("/budgets/{budget_id}/lines", response_model=BudgetOut, status_code=201)
def add_line(budget_id: uuid.UUID, body: LineIn, request: Request, user: User = Depends(MANAGE),
             db: Session = Depends(get_db)):
    budget = get_owned(db, Budget, budget_id, user)
    _draft(budget)
    if body.cost_code_id:
        get_owned(db, CostCode, body.cost_code_id, user, code=422)
    line = BudgetLine(organization_id=user.organization_id, budget_id=budget.id, category=body.category,
                      cost_code_id=body.cost_code_id, description=body.description,
                      original_amount=body.amount, revised_amount=body.amount)
    db.add(line)
    db.commit()
    log_action(db, action="budget.line.create", org_id=user.organization_id, user_id=user.id,
               entity="budget_line", entity_id=line.id, request=request)
    return _out(db, budget)


@router.patch("/budgets/{budget_id}/lines/{line_id}", response_model=BudgetOut)
def edit_line(budget_id: uuid.UUID, line_id: uuid.UUID, body: LineUpdate, request: Request,
              user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    budget = get_owned(db, Budget, budget_id, user)
    _draft(budget)
    line = get_owned(db, BudgetLine, line_id, user)
    if line.budget_id != budget.id:
        raise HTTPException(404, "BudgetLine not found")
    line.original_amount = line.revised_amount = body.amount
    db.commit()
    log_action(db, action="budget.line.update", org_id=user.organization_id, user_id=user.id,
               entity="budget_line", entity_id=line.id, request=request)
    return _out(db, budget)


@router.post("/budgets/{budget_id}/approve", response_model=BudgetOut)
def approve(budget_id: uuid.UUID, request: Request, user: User = Depends(APPROVE), db: Session = Depends(get_db)):
    budget = get_owned(db, Budget, budget_id, user)
    _draft(budget)
    lines = _lines(db, budget)
    if not lines:
        raise HTTPException(422, "Cannot approve a budget without lines")
    for l in lines:
        l.original_amount = l.revised_amount  # freeze the baseline
    budget.status = ApprovalStatus.APPROVED
    budget.approved_by = user.id
    budget.approved_at = datetime.now(timezone.utc)
    db.commit()
    log_action(db, action="budget.approve", org_id=user.organization_id, user_id=user.id, entity="budget",
               entity_id=budget.id, request=request)
    return _out(db, budget)


@router.post("/budgets/{budget_id}/lines/{line_id}/revise", response_model=BudgetOut)
def revise(budget_id: uuid.UUID, line_id: uuid.UUID, body: Revise, request: Request,
           user: User = Depends(APPROVE), db: Session = Depends(get_db)):
    budget = get_owned(db, Budget, budget_id, user)
    if budget.status != ApprovalStatus.APPROVED:
        raise HTTPException(409, "Only approved budgets are revised; edit lines directly while in draft")
    line = get_owned(db, BudgetLine, line_id, user)
    if line.budget_id != budget.id:
        raise HTTPException(404, "BudgetLine not found")
    if body.new_amount < line.committed_amount:
        raise HTTPException(422, "Revised amount cannot be lower than already committed cost")
    db.add(BudgetRevision(organization_id=user.organization_id, budget_id=budget.id, line_id=line.id,
                          old_amount=line.revised_amount, new_amount=body.new_amount, reason=body.reason,
                          revised_by=user.id))
    old = line.revised_amount
    line.revised_amount = body.new_amount
    db.commit()
    log_action(db, action="budget.revise", org_id=user.organization_id, user_id=user.id, entity="budget_line",
               entity_id=line.id, request=request,
               detail={"old": str(old), "new": str(body.new_amount), "reason": body.reason})
    return _out(db, budget)


@router.get("/budgets/{budget_id}/revisions", response_model=list[RevisionOut])
def revisions(budget_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    budget = get_owned(db, Budget, budget_id, user)
    q = org_scoped(BudgetRevision, user).where(BudgetRevision.budget_id == budget.id).order_by(BudgetRevision.created_at)
    return db.scalars(q).all()
