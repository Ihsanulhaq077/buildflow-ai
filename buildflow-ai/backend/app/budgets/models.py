import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.boq.models import ApprovalStatus, CostCategory
from app.models import Base, BaseMixin

MONEY = Numeric(18, 2)
ZERO = Decimal("0")


class Budget(BaseMixin, Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("project_id"),)  # one budget per project; changes go through revisions
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    boq_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("boqs.id"), nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus, native_enum=False, length=20),
                                                   default=ApprovalStatus.DRAFT)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class BudgetLine(BaseMixin, Base):
    """original_amount is frozen at approval. committed/actual/paid are filled by later phases
    (PO approval, GRN/expenses, payments) and are 0 until then."""
    __tablename__ = "budget_lines"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budgets.id"), index=True)
    category: Mapped[CostCategory] = mapped_column(Enum(CostCategory, native_enum=False, length=20))
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_codes.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(300))
    original_amount: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    revised_amount: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    committed_amount: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    actual_amount: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)
    paid_amount: Mapped[Decimal] = mapped_column(MONEY, default=ZERO)


class BudgetRevision(BaseMixin, Base):
    __tablename__ = "budget_revisions"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budgets.id"), index=True)
    line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budget_lines.id"))
    old_amount: Mapped[Decimal] = mapped_column(MONEY)
    new_amount: Mapped[Decimal] = mapped_column(MONEY)
    reason: Mapped[str] = mapped_column(String(500))
    revised_by: Mapped[uuid.UUID] = mapped_column(Uuid)
