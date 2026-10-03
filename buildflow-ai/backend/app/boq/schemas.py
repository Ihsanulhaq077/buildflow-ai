import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.boq.models import ApprovalStatus, CostCategory

RATE = dict(ge=0, max_digits=18, decimal_places=2)
PCT = dict(ge=0, le=100, max_digits=6, decimal_places=2)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CostCodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=200)
    category: CostCategory


class CostCodeOut(_Out, CostCodeIn):
    id: uuid.UUID


class UnitIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)


class UnitOut(_Out, UnitIn):
    id: uuid.UUID


class ConversionIn(BaseModel):
    from_unit_id: uuid.UUID
    to_unit_id: uuid.UUID
    factor: Decimal = Field(gt=0, max_digits=18, decimal_places=8)

    @model_validator(mode="after")
    def _diff(self):
        if self.from_unit_id == self.to_unit_id:
            raise ValueError("from_unit_id and to_unit_id must differ")
        return self


class ConversionOut(_Out, ConversionIn):
    id: uuid.UUID


class BOQIn(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=2, max_length=200)
    overhead_pct: Decimal = Field(default=Decimal("0"), **PCT)
    contingency_pct: Decimal = Field(default=Decimal("0"), **PCT)
    profit_pct: Decimal = Field(default=Decimal("0"), **PCT)


class BOQUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    overhead_pct: Decimal | None = Field(default=None, **PCT)
    contingency_pct: Decimal | None = Field(default=None, **PCT)
    profit_pct: Decimal | None = Field(default=None, **PCT)


class ItemIn(BaseModel):
    item_code: str = Field(min_length=1, max_length=50)
    trade: str = ""
    description: str = Field(min_length=2, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_id: uuid.UUID
    waste_pct: Decimal = Field(default=Decimal("0"), **PCT)
    material_rate: Decimal = Field(default=Decimal("0"), **RATE)
    labour_rate: Decimal = Field(default=Decimal("0"), **RATE)
    equipment_rate: Decimal = Field(default=Decimal("0"), **RATE)
    cost_code_id: uuid.UUID | None = None


class ItemUpdate(BaseModel):
    trade: str | None = None
    description: str | None = Field(default=None, min_length=2, max_length=500)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=4)
    unit_id: uuid.UUID | None = None
    waste_pct: Decimal | None = Field(default=None, **PCT)
    material_rate: Decimal | None = Field(default=None, **RATE)
    labour_rate: Decimal | None = Field(default=None, **RATE)
    equipment_rate: Decimal | None = Field(default=None, **RATE)
    cost_code_id: uuid.UUID | None = None


class ItemOut(_Out, ItemIn):
    id: uuid.UUID
    unit_rate: Decimal
    amount: Decimal


class SummaryOut(BaseModel):
    material_cost: Decimal
    labour_cost: Decimal
    equipment_cost: Decimal
    direct_cost: Decimal
    overhead: Decimal
    contingency: Decimal
    subtotal: Decimal
    profit: Decimal
    selling_price: Decimal
    gross_margin_pct: Decimal


class BOQOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    status: ApprovalStatus
    overhead_pct: Decimal
    contingency_pct: Decimal
    profit_pct: Decimal
    items: list[ItemOut]
    summary: SummaryOut
