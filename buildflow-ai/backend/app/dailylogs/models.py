import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, BaseMixin


class LogStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class DailyLog(BaseMixin, Base):
    """One report per project per day. Workforce and material movements are *derived* from attendance and the
    stock ledger at read time (not retyped), so the report cannot drift from the system of record."""
    __tablename__ = "daily_logs"
    __table_args__ = (UniqueConstraint("organization_id", "project_id", "log_date"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    log_date: Mapped[date] = mapped_column(Date)
    status: Mapped[LogStatus] = mapped_column(Enum(LogStatus, native_enum=False, length=20), default=LogStatus.DRAFT)
    weather: Mapped[str] = mapped_column(String(100), default="")
    work_completed: Mapped[str] = mapped_column(Text, default="")
    equipment: Mapped[str] = mapped_column(Text, default="")
    issues: Mapped[str] = mapped_column(Text, default="")
    safety: Mapped[str] = mapped_column(Text, default="")
    quality: Mapped[str] = mapped_column(Text, default="")
    tomorrow_plan: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyLogProgress(BaseMixin, Base):
    __tablename__ = "daily_log_progress"
    __table_args__ = (UniqueConstraint("log_id", "boq_item_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    log_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("daily_logs.id"), index=True)
    boq_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("boq_items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))  # completed on this day, in the BOQ item's unit
    notes: Mapped[str] = mapped_column(String(300), default="")
