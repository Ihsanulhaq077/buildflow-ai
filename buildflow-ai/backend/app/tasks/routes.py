"""Tasks API - role-scoped task board for dashboards."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.dashboards.models import Dashboard
from app.db import get_db
from app.deps import get_owned, require_permission
from app.models import Role, User
from app.projects.models import Project
from app.tasks.models import TaskStatus
from app.tasks.schemas import TaskIn, TaskOut, TaskUpdate
from app.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])

READ = require_permission("tasks.read")
MANAGE = require_permission("tasks.manage")


def get_service(db: Session = Depends(get_db), user: User = Depends(READ)) -> TaskService:
    return TaskService(db, user)


@router.get("", response_model=list[TaskOut])
def list_tasks(
    dashboard_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    task_status: str | None = None,
    assigned_to_me: bool = False,
    mine: bool = False,
    service: TaskService = Depends(get_service),
):
    """List tasks visible to the caller. Visibility is scoped by role, dashboard and assignment."""
    if dashboard_id:
        get_owned(service.db, Dashboard, dashboard_id, service.user, code=422)
    if project_id:
        get_owned(service.db, Project, project_id, service.user, code=422)
    try:
        status_filter = TaskStatus(task_status) if task_status else None
    except ValueError:
        raise HTTPException(422, f"Unknown status '{task_status}'")
    return service.list_tasks(dashboard_id=dashboard_id, project_id=project_id,
                              status=status_filter, assigned_to_me=assigned_to_me, mine=mine)


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskIn, request: Request, user: User = Depends(MANAGE),
                db: Session = Depends(get_db)):
    """Create a task on a role dashboard."""
    if body.dashboard_id:
        get_owned(db, Dashboard, body.dashboard_id, user, code=422)
    if body.project_id:
        get_owned(db, Project, body.project_id, user, code=422)
    if body.assigned_to:
        get_owned(db, User, body.assigned_to, user, code=422)
    if body.target_role:
        role = db.scalar(select(Role).where(Role.organization_id == user.organization_id,
                                            Role.name == body.target_role))
        if role is None:
            raise HTTPException(422, f"Unknown role '{body.target_role}'")
    service = TaskService(db, user)
    task = service.create_task(body.model_dump())
    log_action(db, action="task.create", org_id=user.organization_id, user_id=user.id, entity="task",
               entity_id=task.id, request=request, detail={"title": task.title})
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: uuid.UUID, service: TaskService = Depends(get_service)):
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.put("/{task_id}", response_model=TaskOut)
@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: uuid.UUID, body: TaskUpdate, request: Request,
                user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    service = TaskService(db, user)
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    data = body.model_dump(exclude_unset=True)
    if "dashboard_id" in data and data["dashboard_id"]:
        get_owned(db, Dashboard, data["dashboard_id"], user, code=422)
    if "project_id" in data and data["project_id"]:
        get_owned(db, Project, data["project_id"], user, code=422)
    if "assigned_to" in data and data["assigned_to"]:
        get_owned(db, User, data["assigned_to"], user, code=422)
    task = service.update_task(task, data)
    log_action(db, action="task.update", org_id=user.organization_id, user_id=user.id, entity="task",
               entity_id=task.id, request=request)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, request: Request, user: User = Depends(MANAGE),
                db: Session = Depends(get_db)):
    service = TaskService(db, user)
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    service.delete_task(task)
    log_action(db, action="task.delete", org_id=user.organization_id, user_id=user.id, entity="task",
               entity_id=task.id, request=request)
    return None
