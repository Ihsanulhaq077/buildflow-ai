import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.tasks.models import TaskPriority, TaskStatus


class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    dashboard_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    target_role: str | None = Field(default=None, max_length=50)
    assigned_to: uuid.UUID | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    dashboard_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    target_role: str | None = Field(default=None, max_length=50)
    assigned_to: uuid.UUID | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    dashboard_id: uuid.UUID | None
    project_id: uuid.UUID | None
    target_role: str | None
    assigned_to: uuid.UUID | None
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    created_by: uuid.UUID | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
