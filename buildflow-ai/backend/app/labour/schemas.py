import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.labour.models import AttendanceStatus, SheetStatus

RATE = dict(ge=0, max_digits=18, decimal_places=2)


class WorkerIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=200)
    trade: str = ""
    contractor: str = ""
    phone: str = ""
    daily_rate: Decimal = Field(default=Decimal("0"), **RATE)
    overtime_rate: Decimal = Field(default=Decimal("0"), **RATE)
    cost_code_id: uuid.UUID | None = None


class WorkerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    trade: str | None = None
    contractor: str | None = None
    phone: str | None = None
    daily_rate: Decimal | None = Field(default=None, **RATE)
    overtime_rate: Decimal | None = Field(default=None, **RATE)
    cost_code_id: uuid.UUID | None = None
    is_active: bool | None = None


class WorkerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    trade: str
    contractor: str
    phone: str
    is_active: bool
    cost_code_id: uuid.UUID | None
    daily_rate: Decimal | None = None      # hidden without labour.cost.read
    overtime_rate: Decimal | None = None


class EntryIn(BaseModel):
    worker_id: uuid.UUID
    status: AttendanceStatus
    overtime_hours: Decimal = Field(default=Decimal("0"), ge=0, le=16, max_digits=5, decimal_places=2)
    cost_code_id: uuid.UUID | None = None


class SheetIn(BaseModel):
    project_id: uuid.UUID
    work_date: date
    entries: list[EntryIn] = Field(default_factory=list, max_length=500)


class EntriesIn(BaseModel):
    entries: list[EntryIn] = Field(max_length=500)


class RejectIn(BaseModel):
    comment: str = Field(min_length=3, max_length=500)


class EntryOut(BaseModel):
    worker_id: uuid.UUID
    worker_code: str
    worker_name: str
    status: AttendanceStatus
    days: Decimal
    overtime_hours: Decimal
    cost_code_id: uuid.UUID | None
    cost: Decimal | None = None            # hidden without labour.cost.read


class SheetOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    work_date: date
    status: SheetStatus
    decision_comment: str
    present: int
    half_day: int
    absent: int
    leave: int
    total_days: Decimal
    total_overtime_hours: Decimal
    total_cost: Decimal | None = None
    entries: list[EntryOut]
