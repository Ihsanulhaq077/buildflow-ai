"""Task service - role-scoped visibility and CRUD.

Visibility rule
---------------
A task is visible to a user when ANY of these hold:

1. The user is an OWNER (or holds ``tasks.manage`` with org-wide reach) -> sees every task.
2. The task is pinned to a dashboard the user is allowed to see.
3. The task targets the user's role (``target_role == user.role.name``).
4. The task is assigned directly to the user.
5. The task is org-wide (no dashboard, no target role, no assignee).

Rule 5 is what makes a task created by an owner show up for everyone who has no more
specific reason to see it.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.dashboards.models import Dashboard
from app.models import User
from app.tasks.models import Task, TaskPriority, TaskStatus


class TaskService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.org_id = user.organization_id

    # --- visibility helpers ---

    @property
    def _is_owner(self) -> bool:
        return bool(self.user.role and self.user.role.name == "OWNER")

    def _visible_dashboard_ids(self) -> list[uuid.UUID]:
        """Dashboards this user can see: role-targeted, public, explicitly granted, or their own."""
        role_name = self.user.role.name if self.user.role else None
        q = select(Dashboard.id).where(
            Dashboard.organization_id == self.org_id,
            Dashboard.is_active.is_(True),
        )
        if not self._is_owner:
            q = q.where(or_(
                Dashboard.target_role == role_name,
                Dashboard.is_public.is_(True),
                Dashboard.created_by == self.user.id,
            ))
        return list(self.db.scalars(q))

    def _visibility_clause(self):
        if self._is_owner:
            return None  # no restriction
        role_name = self.user.role.name if self.user.role else None
        dashboard_ids = self._visible_dashboard_ids()
        return or_(
            Task.assigned_to == self.user.id,
            Task.created_by == self.user.id,
            Task.target_role == role_name,
            Task.dashboard_id.in_(dashboard_ids) if dashboard_ids else False,
            (Task.dashboard_id.is_(None)) & (Task.target_role.is_(None)) & (Task.assigned_to.is_(None)),
        )

    # --- CRUD ---

    def list_tasks(self, dashboard_id: uuid.UUID | None = None,
                   project_id: uuid.UUID | None = None,
                   status: str | None = None,
                   assigned_to_me: bool = False,
                   mine: bool = False) -> list[Task]:
        q = select(Task).where(Task.organization_id == self.org_id, Task.is_active.is_(True))
        clause = self._visibility_clause()
        if clause is not None:
            q = q.where(clause)
        if dashboard_id:
            q = q.where(Task.dashboard_id == dashboard_id)
        if project_id:
            q = q.where(Task.project_id == project_id)
        if status:
            q = q.where(Task.status == status)
        if assigned_to_me:
            q = q.where(Task.assigned_to == self.user.id)
        if mine:
            q = q.where(or_(Task.assigned_to == self.user.id, Task.target_role == (
                self.user.role.name if self.user.role else None)))
        return list(self.db.scalars(q.order_by(Task.created_at.desc())))

    def get_task(self, task_id: uuid.UUID) -> Task | None:
        q = select(Task).where(Task.id == task_id,
                               Task.organization_id == self.org_id,
                               Task.is_active.is_(True))
        clause = self._visibility_clause()
        if clause is not None:
            q = q.where(clause)
        return self.db.scalar(q)

    def create_task(self, data: dict) -> Task:
        task = Task(
            organization_id=self.org_id,
            dashboard_id=data.get("dashboard_id"),
            project_id=data.get("project_id"),
            target_role=data.get("target_role"),
            assigned_to=data.get("assigned_to"),
            title=data["title"],
            description=data.get("description", ""),
            status=data.get("status", TaskStatus.TODO),
            priority=data.get("priority", TaskPriority.MEDIUM),
            due_date=data.get("due_date"),
            created_by=self.user.id,
        )
        if task.status == TaskStatus.DONE:
            task.completed_at = datetime.now(timezone.utc)
        self.db.add(task)
        self.db.commit()
        return task

    def update_task(self, task: Task, data: dict) -> Task:
        for key, value in data.items():
            if not hasattr(task, key):
                continue
            # Columns that must not be nulled out. Everything else (dashboard_id, project_id,
            # target_role, assigned_to, due_date) may be cleared by passing an explicit null.
            if value is None and key in ("title", "status", "priority"):
                continue
            setattr(task, key, value)
        if "status" in data and data["status"] is not None:
            if data["status"] == TaskStatus.DONE and task.completed_at is None:
                task.completed_at = datetime.now(timezone.utc)
            elif data["status"] != TaskStatus.DONE:
                task.completed_at = None
        self.db.commit()
        return task

    def delete_task(self, task: Task) -> None:
        task.is_active = False
        self.db.commit()
