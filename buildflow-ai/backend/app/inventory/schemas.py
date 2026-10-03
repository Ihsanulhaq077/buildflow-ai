import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.inventory.models import MovementType

Q = dict(gt=0, max_digits=18, decimal_places=4)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WarehouseIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    address: str = ""
    project_id: uuid.UUID | None = None


class WarehouseOut(_Out, WarehouseIn):
    id: uuid.UUID


class ItemIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    unit_id: uuid.UUID
    cost_code_id: uuid.UUID | None = None
    min_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    max_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)

    @model_validator(mode="after")
    def _levels(self):
        if self.max_stock and self.max_stock < self.min_stock:
            raise ValueError("max_stock must be >= min_stock")
        return self


class ItemOut(_Out, ItemIn):
    id: uuid.UUID


class LineQty(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(**Q)


class MovementIn(BaseModel):  # issue / return
    warehouse_id: uuid.UUID
    project_id: uuid.UUID
    lines: list[LineQty] = Field(min_length=1, max_length=100)
    note: str = ""


class TransferIn(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    lines: list[LineQty] = Field(min_length=1, max_length=100)
    note: str = ""

    @model_validator(mode="after")
    def _diff(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError("Warehouses must differ")
        return self


class AdjustIn(BaseModel):
    warehouse_id: uuid.UUID
    item_id: uuid.UUID
    kind: Literal["OPENING_STOCK", "INCREASE", "DECREASE", "DAMAGE", "WASTE"]
    quantity: Decimal = Field(**Q)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    reason: str = Field(min_length=5, max_length=500)
    project_id: uuid.UUID | None = None


class MovementLineOut(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal
    unit_cost: Decimal


class MovementOut(BaseModel):
    id: uuid.UUID
    number: str
    kind: str
    warehouse_id: uuid.UUID
    project_id: uuid.UUID
    lines: list[MovementLineOut]


class StockOut(BaseModel):
    warehouse_id: uuid.UUID
    item_id: uuid.UUID
    item_code: str
    item_name: str
    quantity: Decimal
    avg_cost: Decimal
    value: Decimal
    reorder_level: Decimal
    below_reorder: bool


class TxOut(_Out):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    item_id: uuid.UUID
    type: MovementType
    quantity: Decimal
    unit_cost: Decimal
    project_id: uuid.UUID | None
    reference_type: str
    reference_id: str
    note: str
    created_by: uuid.UUID | None
    created_at: datetime


class ConsumptionOut(BaseModel):
    item_id: uuid.UUID
    item_code: str
    issued: Decimal
    returned: Decimal
    net_quantity: Decimal
    net_cost: Decimal
