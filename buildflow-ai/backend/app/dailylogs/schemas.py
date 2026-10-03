import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.dailylogs.models import LogStatus

TXT = dict(default="", max_length=5000)


class ProgressIn(BaseModel):
    boq_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    notes: str = Field(default="", max_length=300)


class LogBody(BaseModel):
    site_id: uuid.UUID | None = None
    weather: str = Field(default="", max_length=100)
    work_completed: str = Field(**TXT)
    equipment: str = Field(**TXT)
    issues: str = Field(**TXT)
    safety: str = Field(**TXT)
    quality: str = Field(**TXT)
    tomorrow_plan: str = Field(**TXT)
    progress: list[ProgressIn] = Field(default_factory=list, max_length=200)


class LogCreate(LogBody):
    project_id: uuid.UUID
    log_date: date


class ReopenIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ProgressOut(BaseModel):
    boq_item_id: uuid.UUID
    item_code: str
    description: str
    quantity_today: Decimal
    cumulative: Decimal
    boq_quantity: Decimal
    percent: Decimal
    notes: str


class LogOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    site_id: uuid.UUID | None
    log_date: date
    status: LogStatus
    weather: str
    work_completed: str
    equipment: str
    issues: str
    safety: str
    quality: str
    tomorrow_plan: str
    progress: list[ProgressOut]
    workforce: dict
    materials: dict
