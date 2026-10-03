import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.procurement.models import POStatus, ReqStatus

Q = dict(gt=0, max_digits=18, decimal_places=4)
RATE = dict(ge=0, max_digits=18, decimal_places=2)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SupplierIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    contact_person: str = ""
    phone: str = ""
    email: str = ""


class SupplierOut(_Out, SupplierIn):
    id: uuid.UUID
    is_approved: bool


class ReqLineIn(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(**Q)
    boq_item_id: uuid.UUID | None = None
    notes: str = ""


class ReqIn(BaseModel):
    project_id: uuid.UUID
    warehouse_id: uuid.UUID
    lines: list[ReqLineIn] = Field(min_length=1, max_length=100)
    notes: str = ""


class Decision(BaseModel):
    comment: str = Field(default="", max_length=500)


class RejectIn(BaseModel):
    comment: str = Field(min_length=3, max_length=500)


class ReqLineOut(_Out):
    id: uuid.UUID
    item_id: uuid.UUID
    quantity: Decimal
    boq_item_id: uuid.UUID | None
    stock_on_hand: Decimal
    on_order: Decimal
    shortage_qty: Decimal
    exceeds_boq: bool
    notes: str


class ReqOut(BaseModel):
    id: uuid.UUID
    number: str
    project_id: uuid.UUID
    warehouse_id: uuid.UUID
    status: ReqStatus
    notes: str
    requested_by: uuid.UUID
    decision_comment: str
    lines: list[ReqLineOut]


class StockCheckOut(BaseModel):
    item_id: uuid.UUID
    requested: Decimal
    stock_on_hand: Decimal
    on_order: Decimal
    shortage_qty: Decimal


class QuoteLineIn(BaseModel):
    requisition_line_id: uuid.UUID
    unit_rate: Decimal = Field(**RATE)


class QuoteIn(BaseModel):
    supplier_id: uuid.UUID
    valid_until: date | None = None
    notes: str = ""
    lines: list[QuoteLineIn] = Field(min_length=1, max_length=100)


class POLineIn(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(**Q)
    unit_rate: Decimal = Field(**RATE)


class POIn(BaseModel):
    project_id: uuid.UUID
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    lines: list[POLineIn] = Field(min_length=1, max_length=100)


class POFromQuote(BaseModel):
    quote_id: uuid.UUID


class POLineOut(_Out):
    id: uuid.UUID
    item_id: uuid.UUID
    quantity: Decimal
    unit_rate: Decimal
    received_qty: Decimal
    amount: Decimal


class POOut(BaseModel):
    id: uuid.UUID
    number: str
    project_id: uuid.UUID
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    requisition_id: uuid.UUID | None
    status: POStatus
    total_amount: Decimal
    decision_comment: str
    lines: list[POLineOut]


class GRNLineIn(BaseModel):
    po_line_id: uuid.UUID
    quantity_accepted: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    quantity_rejected: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)


class GRNIn(BaseModel):
    po_id: uuid.UUID
    delivery_note: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=500)
    lines: list[GRNLineIn] = Field(min_length=1, max_length=100)


class GRNLineOut(_Out):
    po_line_id: uuid.UUID
    item_id: uuid.UUID
    quantity_accepted: Decimal
    quantity_rejected: Decimal
    unit_rate: Decimal


class GRNOut(BaseModel):
    id: uuid.UUID
    number: str
    po_id: uuid.UUID
    warehouse_id: uuid.UUID
    delivery_note: str
    po_status: POStatus
    lines: list[GRNLineOut]
