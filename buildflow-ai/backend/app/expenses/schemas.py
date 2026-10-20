import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.boq.models import CostCategory
from app.expenses.models import ExpenseStatus

AMOUNT = dict(ge=0, max_digits=18, decimal_places=2)


class ExpenseIn(BaseModel):
    project_id: uuid.UUID
    cost_code_id: uuid.UUID | None = None
    description: str = Field(min_length=2, max_length=300)
    category: CostCategory = CostCategory.OTHER
    amount: Decimal = Field(**AMOUNT)
    expense_date: date
    vendor: str = Field(default="", max_length=200)
    reference_no: str = Field(default="", max_length=100)
    payment_method: str = Field(default="", max_length=30)
    notes: str = Field(default="", max_length=2000)
    is_billable: bool = False


class ExpenseUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    cost_code_id: uuid.UUID | None = None
    description: str | None = Field(default=None, min_length=2, max_length=300)
    category: CostCategory | None = None
    amount: Decimal | None = Field(default=None, **AMOUNT)
    expense_date: date | None = None
    vendor: str | None = Field(default=None, max_length=200)
    reference_no: str | None = Field(default=None, max_length=100)
    payment_method: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)
    is_billable: bool | None = None


class ExpenseDecision(BaseModel):
    approve: bool
    comment: str = Field(default="", max_length=500)


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    cost_code_id: uuid.UUID | None
    expense_no: str
    description: str
    category: CostCategory
    amount: Decimal
    expense_date: date
    vendor: str
    reference_no: str
    payment_method: str
    notes: str
    status: ExpenseStatus
    is_billable: bool
    created_by: uuid.UUID | None
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    decision_comment: str
    created_at: datetime
    updated_at: datetime


class ExpenseSummary(BaseModel):
    """Aggregate view of expenses for the accountant dashboard."""

    total_count: int = 0
    total_amount: Decimal = Decimal("0")
    by_status: dict[str, int] = {}
    by_category: dict[str, Decimal] = {}
    by_project: dict[str, Decimal] = {}
    billable_amount: Decimal = Decimal("0")
    pending_approval_count: int = 0
    pending_approval_amount: Decimal = Decimal("0")
