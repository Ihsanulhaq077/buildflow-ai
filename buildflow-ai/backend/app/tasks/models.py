"""Task models for role-specific dashboards.

A task is a unit of work that appears on a role's dashboard. It may optionally be pinned to a
specific dashboard (so it shows up in that cockpit only) and/or targeted at a role (so every
member of that role sees it) and/or assigned to a specific user.
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, BaseMixin


class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Task(BaseMixin, Base):
    __tablename__ = "tasks"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    # Optional: pin the task to one dashboard (the role cockpit it belongs to).
    dashboard_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"), index=True, nullable=True)
    # Optional: the project the task belongs to.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), index=True, nullable=True)
    # Optional: the role this task is intended for. A task with a target_role is visible to
    # every member of that role; a task with an assigned_to is visible to that person.
    target_role: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20), default=TaskStatus.TODO)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, native_enum=False, length=20), default=TaskPriority.MEDIUM)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
