import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.projects.models import ProjectStatus


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClientIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    contact_person: str = ""
    phone: str = ""
    email: str = ""


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None


class ClientOut(_Out, ClientIn):
    id: uuid.UUID


class ProjectIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    client_id: uuid.UUID | None = None
    location: str = ""
    contract_value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    start_date: date | None = None
    planned_end_date: date | None = None
    project_manager_id: uuid.UUID | None = None
    engineer_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.planned_end_date and self.planned_end_date < self.start_date:
            raise ValueError("planned_end_date must be on or after start_date")
        return self


class ProjectUpdate(BaseModel):  # note: no status / organization_id here on purpose
    name: str | None = Field(default=None, min_length=2, max_length=200)
    client_id: uuid.UUID | None = None
    location: str | None = None
    contract_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    start_date: date | None = None
    planned_end_date: date | None = None
    project_manager_id: uuid.UUID | None = None
    engineer_id: uuid.UUID | None = None


class ProjectOut(_Out):
    id: uuid.UUID
    code: str
    name: str
    client_id: uuid.UUID | None
    location: str
    status: ProjectStatus
    contract_value: Decimal
    start_date: date | None
    planned_end_date: date | None
    project_manager_id: uuid.UUID | None
    engineer_id: uuid.UUID | None


class StatusChange(BaseModel):
    status: ProjectStatus


class SiteIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    address: str = ""


class SiteOut(_Out, SiteIn):
    id: uuid.UUID
    project_id: uuid.UUID


class ContractIn(BaseModel):
    contract_no: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=2, max_length=300)
    value: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    retention_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=6, decimal_places=2)
    signed_date: date | None = None


class ContractOut(_Out, ContractIn):
    id: uuid.UUID
    project_id: uuid.UUID
