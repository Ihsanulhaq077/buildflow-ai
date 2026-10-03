import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, BaseMixin

MONEY = Numeric(18, 2)


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    HALF_DAY = "HALF_DAY"
    LEAVE = "LEAVE"


DAYS = {AttendanceStatus.PRESENT: Decimal("1"), AttendanceStatus.HALF_DAY: Decimal("0.5"),
        AttendanceStatus.ABSENT: Decimal("0"), AttendanceStatus.LEAVE: Decimal("0")}


class SheetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"


class Worker(BaseMixin, Base):
    __tablename__ = "workers"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    trade: Mapped[str] = mapped_column(String(100), default="")
    contractor: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    daily_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    overtime_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))  # PKR per hour, explicit (no assumed multiplier)
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_codes.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AttendanceSheet(BaseMixin, Base):
    __tablename__ = "attendance_sheets"
    __table_args__ = (UniqueConstraint("organization_id", "project_id", "work_date"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    work_date: Mapped[date] = mapped_column(Date)
    status: Mapped[SheetStatus] = mapped_column(Enum(SheetStatus, native_enum=False, length=20), default=SheetStatus.DRAFT)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_comment: Mapped[str] = mapped_column(String(500), default="")


class AttendanceEntry(BaseMixin, Base):
    """Rates are snapshotted when the entry is saved, so later wage changes never rewrite history."""
    __tablename__ = "attendance_entries"
    __table_args__ = (UniqueConstraint("sheet_id", "worker_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attendance_sheets.id"), index=True)
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id"), index=True)
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus, native_enum=False, length=20))
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_codes.id"), nullable=True)
    days: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))
    daily_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    overtime_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
