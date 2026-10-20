"""Expenses API - accountant module for expense tracking and approval."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import log_action
from app.boq.models import CostCode
from app.db import get_db
from app.deps import get_owned, require_permission
from app.expenses import service as exp_service
from app.expenses.models import ExpenseStatus
from app.expenses.schemas import (ExpenseDecision, ExpenseIn, ExpenseOut, ExpenseSummary,
                                  ExpenseUpdate)
from app.models import User
from app.projects.models import Project

router = APIRouter(prefix="/expenses", tags=["expenses"])

READ = require_permission("expenses.read")
MANAGE = require_permission("expenses.manage")
APPROVE = require_permission("expenses.manage")  # accountant approves expenses too


def get_service(db: Session = Depends(get_db), user: User = Depends(READ)) -> exp_service.ExpenseService:
    return exp_service.ExpenseService(db, user)


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(READ),
):
    svc = exp_service.ExpenseService(db, user)
    try:
        status_enum = ExpenseStatus(status) if status else None
    except ValueError:
        raise HTTPException(422, f"Unknown status '{status}'")
    return svc.list_expenses(
        project_id=project_id, status=status_enum, category=category,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None)


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(body: ExpenseIn, request: Request, user: User = Depends(MANAGE),
                    db: Session = Depends(get_db)):
    if body.project_id:
        get_owned(db, Project, body.project_id, user, code=422)
    if body.cost_code_id:
        get_owned(db, CostCode, body.cost_code_id, user, code=422)
    svc = exp_service.ExpenseService(db, user)
    expense = svc.create_expense(body.model_dump())
    log_action(db, action="expense.create", org_id=user.organization_id, user_id=user.id, entity="expense",
              entity_id=expense.id, request=request, detail={"no": expense.expense_no})
    return expense


@router.get("/summary", response_model=ExpenseSummary)
def summary(db: Session = Depends(get_db), user: User = Depends(READ)):
    svc = exp_service.ExpenseService(db, user)
    rows = svc.list_expenses()
    return ExpenseSummary(**svc.summary(rows))


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(READ)):
    svc = exp_service.ExpenseService(db, user)
    expense = svc.get_expense(expense_id)
    if expense is None:
        raise HTTPException(404, "Expense not found")
    return expense


@router.put("/{expense_id}", response_model=ExpenseOut)
@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: uuid.UUID, body: ExpenseUpdate, request: Request,
                   user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    svc = exp_service.ExpenseService(db, user)
    expense = svc.get_expense(expense_id)
    if expense is None:
        raise HTTPException(404, "Expense not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "project_id" and value:
            get_owned(db, Project, value, user, code=422)
        if key == "cost_code_id" and value:
            get_owned(db, CostCode, value, user, code=422)
    if data.get("project_id"):
        get_owned(db, Project, data["project_id"], user, code=422)
    expense = svc.update_expense(expense, data)
    log_action(db, action="expense.update", org_id=user.organization_id, user_id=user.id, entity="expense",
               entity_id=expense.id, request=request)
    return expense


@router.post("/{expense_id}/decide", response_model=ExpenseOut)
def decide(expense_id: uuid.UUID, body: ExpenseDecision, request: Request,
           user: User = Depends(APPROVE), db: Session = Depends(get_db)):
    svc = exp_service.ExpenseService(db, user)
    expense = svc.get_expense(expense_id)
    if expense is None:
        raise HTTPException(404, "Expense not found")
    try:
        approve = bool(body.approve)
    except ValueError:
        raise HTTPException(422, "Approve must be a boolean")
    decision = ExpenseDecision(approve=approve, comment=body.comment or "")
    expense = svc.decide(expense, decision.approve, decision.comment)
    log_action(db, action="expense.decide", org_id=user.organization_id, user_id=user.id,
               entity="expense", entity_id=expense.id, request=request,
               detail={"approved": approve, "comment": expense.decision_comment})
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: uuid.UUID, request: Request, user: User = Depends(MANAGE),
                  db: Session = Depends(get_db)):
    svc = exp_service.ExpenseService(db, user)
    expense = svc.get_expense(expense_id)
    if expense is None:
        raise HTTPException(404, "Expense not found")
    svc.delete_expense(expense)
    log_action(db, action="expense.delete", org_id=user.organization_id, user_id=user.id,
               entity="expense", entity_id=expense.id, request=request)
    return None
