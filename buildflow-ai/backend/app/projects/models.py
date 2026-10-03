import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, BaseMixin

MONEY = Numeric(18, 2)


class ProjectStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    TENDER = "TENDER"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


ALLOWED_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.DRAFT: {ProjectStatus.TENDER, ProjectStatus.APPROVED, ProjectStatus.CLOSED},
    ProjectStatus.TENDER: {ProjectStatus.APPROVED, ProjectStatus.CLOSED},
    ProjectStatus.APPROVED: {ProjectStatus.ACTIVE, ProjectStatus.CLOSED},
    ProjectStatus.ACTIVE: {ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED},
    ProjectStatus.ON_HOLD: {ProjectStatus.ACTIVE, ProjectStatus.CLOSED},
    ProjectStatus.COMPLETED: {ProjectStatus.CLOSED},
    ProjectStatus.CLOSED: set(),
}


class Client(BaseMixin, Base):
    __tablename__ = "clients"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    contact_person: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Project(BaseMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    location: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus, native_enum=False, length=20),
                                                  default=ProjectStatus.DRAFT)
    contract_value: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    project_manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    engineer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Site(BaseMixin, Base):
    __tablename__ = "sites"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")


class Contract(BaseMixin, Base):
    __tablename__ = "contracts"
    __table_args__ = (UniqueConstraint("organization_id", "contract_no"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    contract_no: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(300))
    value: Mapped[Decimal] = mapped_column(MONEY)
    retention_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
