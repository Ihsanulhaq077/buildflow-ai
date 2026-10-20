"""Expense service - CRUD, approval workflow and budget posting."""
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.boq.models import CostCode
from app.budgets import service as budget_service
from app.expenses.models import Expense, ExpenseStatus
from app.models import User
from app.projects.models import Project

ZERO = Decimal("0")


class ExpenseService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.org_id = user.organization_id

    def _next_no(self) -> str:
        prefix = "EXP"
        count = len(list(self.db.scalars(
            select(Expense.id).where(Expense.organization_id == self.org_id))))
        return f"{prefix}-{count + 1:05d}"

    def list_expenses(self, project_id: uuid.UUID | None = None,
                      status: ExpenseStatus | None = None,
                      category: str | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None) -> list[Expense]:
        q = select(Expense).where(Expense.organization_id == self.org_id,
                                  Expense.is_active.is_(True))
        if project_id:
            q = q.where(Expense.project_id == project_id)
        if status:
            q = q.where(Expense.status == status)
        if category:
            q = q.where(Expense.category == category)
        if date_from:
            q = q.where(Expense.expense_date >= date_from)
        if date_to:
            q = q.where(Expense.expense_date <= date_to)
        return list(self.db.scalars(q.order_by(Expense.expense_date.desc(), Expense.created_at.desc())))

    def get_expense(self, expense_id: uuid.UUID) -> Expense | None:
        return self.db.scalar(select(Expense).where(
            Expense.id == expense_id,
            Expense.organization_id == self.org_id,
            Expense.is_active.is_(True)))

    def create_expense(self, data: dict) -> Expense:
        expense = Expense(
            organization_id=self.org_id,
            expense_no=self._next_no(),
            project_id=data["project_id"],
            cost_code_id=data.get("cost_code_id"),
            description=data["description"],
            category=data.get("category", "OTHER"),
            amount=data["amount"],
            expense_date=data["expense_date"],
            vendor=data.get("vendor", ""),
            reference_no=data.get("reference_no", ""),
            payment_method=data.get("payment_method", ""),
            notes=data.get("notes", ""),
            is_billable=data.get("is_billable", False),
            status=ExpenseStatus.SUBMITTED,
            created_by=self.user.id,
        )
        self.db.add(expense)
        self.db.commit()
        return expense

    def update_expense(self, expense: Expense, data: dict) -> Expense:
        if expense.status == ExpenseStatus.APPROVED:
            raise HTTPException(409, "Approved expenses can no longer be edited")
        for key, value in data.items():
            if not hasattr(expense, key):
                continue
            # Columns that must not be nulled out. Everything else (cost_code_id, vendor,
            # reference_no, payment_method, notes) may be cleared by passing an explicit null.
            if value is None and key in ("project_id", "description", "amount", "expense_date",
                                         "category", "status", "expense_no"):
                continue
            setattr(expense, key, value)
        self.db.commit()
        return expense

    def decide(self, expense: Expense, approve: bool, comment: str = "") -> Expense:
        """Approve or reject. Approval posts the amount to the linked budget line (actual cost)."""
        if expense.status == ExpenseStatus.APPROVED:
            raise HTTPException(409, "Expense has already been approved")
        if expense.status == ExpenseStatus.REJECTED:
            raise HTTPException(409, "Rejected expenses cannot be re-decided")

        if approve:
            if expense.cost_code_id:
                # The cost is already incurred, so a missing budget line must not block the
                # approval. It is flagged on the expense for the accountant to pick up.
                unposted = budget_service.record_actual_soft(
                    self.db, self.org_id, expense.project_id,
                    {expense.cost_code_id: expense.amount})
                if unposted:
                    flag = ("Approved without a budget posting: no approved budget line for "
                            "this project and cost code.")
                    expense.notes = f"{expense.notes}\n{flag}".strip()
            expense.status = ExpenseStatus.APPROVED
        else:
            expense.status = ExpenseStatus.REJECTED
        expense.decision_comment = comment
        expense.decided_by = self.user.id
        expense.decided_at = datetime.now(timezone.utc)
        self.db.commit()
        return expense

    def delete_expense(self, expense: Expense) -> None:
        if expense.status == ExpenseStatus.APPROVED:
            raise HTTPException(409, "Approved expenses cannot be deleted; they are part of the audit trail")
        expense.is_active = False
        self.db.commit()

    def summary(self, expenses: list[Expense]) -> dict:
        by_status: dict[str, int] = defaultdict(int)
        by_category: dict[str, Decimal] = defaultdict(lambda: ZERO)
        by_project: dict[str, Decimal] = defaultdict(lambda: ZERO)
        total = ZERO
        billable = ZERO
        pending_count = 0
        pending_amount = ZERO

        for e in expenses:
            by_status[e.status.value] += 1
            by_category[e.category.value] += e.amount
            by_project[str(e.project_id)] += e.amount
            total += e.amount
            if e.is_billable:
                billable += e.amount
            if e.status == ExpenseStatus.SUBMITTED:
                pending_count += 1
                pending_amount += e.amount

        # Resolve project names for the summary
        project_names: dict[str, str] = {}
        pids = [uuid.UUID(p) for p in by_project]
        if pids:
            for p in self.db.scalars(select(Project).where(Project.id.in_(pids))):
                project_names[str(p.id)] = p.name

        return {
            "total_count": len(expenses),
            "total_amount": total,
            "by_status": dict(by_status),
            "by_category": {k: v for k, v in by_category.items()},
            "by_project": {project_names.get(k, k): v for k, v in by_project.items()},
            "billable_amount": billable,
            "pending_approval_count": pending_count,
            "pending_approval_amount": pending_amount,
        }
