import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.deps import get_owned, org_scoped, require_permission
from app.models import User
from app.projects.models import ALLOWED_TRANSITIONS, Client, Contract, Project, ProjectStatus, Site
from app.projects.schemas import (ClientIn, ClientOut, ClientUpdate, ContractIn, ContractOut, ProjectIn,
                                  ProjectOut, ProjectUpdate, SiteIn, SiteOut, StatusChange)

router = APIRouter(tags=["projects"])
READ = require_permission("projects.read")
MANAGE = require_permission("projects.manage")


def _check_refs(db, user, client_id=None, pm_id=None, eng_id=None):
    if client_id:
        get_owned(db, Client, client_id, user, code=422)
    for uid in (pm_id, eng_id):
        if uid:
            get_owned(db, User, uid, user, code=422)


def _unique_code(db, user, code, exclude=None):
    q = org_scoped(Project, user).where(Project.code == code)
    hit = db.scalar(q)
    if hit and hit.id != exclude:
        raise HTTPException(409, "Project code already exists")


# ---- clients
@router.post("/clients", response_model=ClientOut, status_code=201)
def create_client(body: ClientIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    c = Client(organization_id=user.organization_id, **body.model_dump())
    db.add(c)
    db.commit()
    log_action(db, action="client.create", org_id=user.organization_id, user_id=user.id, entity="client",
               entity_id=c.id, request=request)
    return c


@router.get("/clients", response_model=list[ClientOut])
def list_clients(limit: int = 100, offset: int = 0, user: User = Depends(READ), db: Session = Depends(get_db)):
    q = org_scoped(Client, user).where(Client.deleted_at.is_(None)).order_by(Client.name).limit(min(limit, 500)).offset(offset)
    return db.scalars(q).all()


@router.patch("/clients/{client_id}", response_model=ClientOut)
def update_client(client_id: uuid.UUID, body: ClientUpdate, request: Request, user: User = Depends(MANAGE),
                  db: Session = Depends(get_db)):
    c = get_owned(db, Client, client_id, user)
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    log_action(db, action="client.update", org_id=user.organization_id, user_id=user.id, entity="client",
               entity_id=c.id, request=request)
    return c


# ---- projects
@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    _check_refs(db, user, body.client_id, body.project_manager_id, body.engineer_id)
    _unique_code(db, user, body.code)
    p = Project(organization_id=user.organization_id, created_by=user.id, **body.model_dump())
    db.add(p)
    db.commit()
    log_action(db, action="project.create", org_id=user.organization_id, user_id=user.id, entity="project",
               entity_id=p.id, request=request)
    return p


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(status: ProjectStatus | None = None, limit: int = 100, offset: int = 0,
                  user: User = Depends(READ), db: Session = Depends(get_db)):
    q = org_scoped(Project, user).where(Project.deleted_at.is_(None))
    if status:
        q = q.where(Project.status == status)
    return db.scalars(q.order_by(Project.created_at.desc()).limit(min(limit, 500)).offset(offset)).all()


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    return get_owned(db, Project, project_id, user)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: uuid.UUID, body: ProjectUpdate, request: Request, user: User = Depends(MANAGE),
                   db: Session = Depends(get_db)):
    p = get_owned(db, Project, project_id, user)
    data = body.model_dump(exclude_unset=True)
    _check_refs(db, user, data.get("client_id"), data.get("project_manager_id"), data.get("engineer_id"))
    start = data.get("start_date", p.start_date)
    end = data.get("planned_end_date", p.planned_end_date)
    if start and end and end < start:
        raise HTTPException(422, "planned_end_date must be on or after start_date")
    if p.status == ProjectStatus.CLOSED:
        raise HTTPException(409, "Closed projects cannot be edited")
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    log_action(db, action="project.update", org_id=user.organization_id, user_id=user.id, entity="project",
               entity_id=p.id, request=request, detail={"fields": list(data)})
    return p


@router.post("/projects/{project_id}/status", response_model=ProjectOut)
def change_status(project_id: uuid.UUID, body: StatusChange, request: Request, user: User = Depends(MANAGE),
                  db: Session = Depends(get_db)):
    p = get_owned(db, Project, project_id, user)
    if body.status not in ALLOWED_TRANSITIONS[p.status]:
        raise HTTPException(409, f"Cannot move project from {p.status.value} to {body.status.value}")
    old = p.status.value
    p.status = body.status
    db.commit()
    log_action(db, action="project.status", org_id=user.organization_id, user_id=user.id, entity="project",
               entity_id=p.id, request=request, detail={"from": old, "to": body.status.value})
    return p


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    p = get_owned(db, Project, project_id, user)
    if p.status != ProjectStatus.DRAFT:
        raise HTTPException(409, "Only DRAFT projects can be deleted")
    p.deleted_at = datetime.now(timezone.utc)
    db.commit()
    log_action(db, action="project.delete", org_id=user.organization_id, user_id=user.id, entity="project",
               entity_id=p.id, request=request)


# ---- sites & contracts
@router.post("/projects/{project_id}/sites", response_model=SiteOut, status_code=201)
def add_site(project_id: uuid.UUID, body: SiteIn, request: Request, user: User = Depends(MANAGE),
             db: Session = Depends(get_db)):
    p = get_owned(db, Project, project_id, user)
    s = Site(organization_id=user.organization_id, project_id=p.id, **body.model_dump())
    db.add(s)
    db.commit()
    log_action(db, action="site.create", org_id=user.organization_id, user_id=user.id, entity="site",
               entity_id=s.id, request=request)
    return s


@router.get("/projects/{project_id}/sites", response_model=list[SiteOut])
def list_sites(project_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    p = get_owned(db, Project, project_id, user)
    return db.scalars(org_scoped(Site, user).where(Site.project_id == p.id)).all()


@router.post("/projects/{project_id}/contracts", response_model=ContractOut, status_code=201)
def add_contract(project_id: uuid.UUID, body: ContractIn, request: Request, user: User = Depends(MANAGE),
                 db: Session = Depends(get_db)):
    p = get_owned(db, Project, project_id, user)
    if db.scalar(org_scoped(Contract, user).where(Contract.contract_no == body.contract_no)):
        raise HTTPException(409, "Contract number already exists")
    c = Contract(organization_id=user.organization_id, project_id=p.id, **body.model_dump())
    db.add(c)
    db.commit()
    log_action(db, action="contract.create", org_id=user.organization_id, user_id=user.id, entity="contract",
               entity_id=c.id, request=request)
    return c


@router.get("/projects/{project_id}/contracts", response_model=list[ContractOut])
def list_contracts(project_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    p = get_owned(db, Project, project_id, user)
    return db.scalars(org_scoped(Contract, user).where(Contract.project_id == p.id)).all()
