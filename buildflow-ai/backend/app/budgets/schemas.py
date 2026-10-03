import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.boq.models import ApprovalStatus, CostCategory

AMOUNT = dict(ge=0, max_digits=18, decimal_places=2)


class FromBOQ(BaseModel):
    boq_id: uuid.UUID


class LineIn(BaseModel):
    category: CostCategory
    cost_code_id: uuid.UUID | None = None
    description: str = Field(min_length=2, max_length=300)
    amount: Decimal = Field(**AMOUNT)


class LineUpdate(BaseModel):
    amount: Decimal = Field(**AMOUNT)


class Revise(BaseModel):
    new_amount: Decimal = Field(**AMOUNT)
    reason: str = Field(min_length=5, max_length=500)


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    category: CostCategory
    cost_code_id: uuid.UUID | None
    description: str
    original_amount: Decimal
    revised_amount: Decimal
    committed_amount: Decimal
    actual_amount: Decimal
    paid_amount: Decimal


class Totals(BaseModel):
    original: Decimal
    revised: Decimal
    committed: Decimal
    actual: Decimal
    paid: Decimal
    remaining: Decimal   # revised - committed
    variance: Decimal    # revised - actual
    contract_value: Decimal
    planned_margin: Decimal      # contract_value - revised
    planned_margin_pct: Decimal  # planned_margin / contract_value * 100 (0 if no contract value)
    by_category: dict[str, Decimal]  # revised amount per category


class BudgetOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    boq_id: uuid.UUID | None
    status: ApprovalStatus
    lines: list[LineOut]
    totals: Totals


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    line_id: uuid.UUID
    old_amount: Decimal
    new_amount: Decimal
    reason: str
    revised_by: uuid.UUID
    created_at: datetime
