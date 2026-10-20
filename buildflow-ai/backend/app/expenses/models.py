"""Expense tracking for the accountant module.

An expense is money spent on a project that is NOT captured by a purchase order or an
approved attendance sheet - the "other costs of doing business": transport, site utilities,
equipment hire, statutory fees, site office running costs, and so on.

Expenses can optionally be linked to a cost code and a budget line. When a cost code is
supplied, approving the expense posts the amount to that budget line's ``actual_amount``,
so the budget always reflects what has really been spent.
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.boq.models import CostCategory
from app.models import Base, BaseMixin

MONEY = Numeric(18, 2)


class ExpenseStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REIMBURSED = "REIMBURSED"


class Expense(BaseMixin, Base):
    __tablename__ = "expenses"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cost_codes.id"), nullable=True, index=True)

    expense_no: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(300))
    category: Mapped[CostCategory] = mapped_column(
        Enum(CostCategory, native_enum=False, length=20), default=CostCategory.OTHER)
    amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    expense_date: Mapped[date] = mapped_column(Date)

    # Optional accounting detail
    vendor: Mapped[str] = mapped_column(String(200), default="")
    reference_no: Mapped[str] = mapped_column(String(100), default="")
    payment_method: Mapped[str] = mapped_column(String(30), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[ExpenseStatus] = mapped_column(
        Enum(ExpenseStatus, native_enum=False, length=20), default=ExpenseStatus.DRAFT)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_comment: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
