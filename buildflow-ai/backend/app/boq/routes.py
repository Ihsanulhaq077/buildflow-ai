import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.boq import calculations as calc
from app.boq.models import BOQ, ApprovalStatus, BOQItem, CostCode, Unit, UnitConversion
from app.boq.schemas import (BOQIn, BOQOut, BOQUpdate, ConversionIn, ConversionOut, CostCodeIn, CostCodeOut,
                             ItemIn, ItemOut, ItemUpdate, SummaryOut, UnitIn, UnitOut)
from app.db import get_db
from app.deps import get_owned, org_scoped, require_permission
from app.models import User
from app.projects.models import Project

router = APIRouter(tags=["boq"])
READ = require_permission("boq.read")
MANAGE = require_permission("boq.manage")
APPROVE = require_permission("boq.approve")
CATALOG = require_permission("catalog.manage")


def _dup(exc_msg: str):
    return HTTPException(409, exc_msg)


# ---- catalog: cost codes, units, conversions
@router.post("/cost-codes", response_model=CostCodeOut, status_code=201)
def create_cost_code(body: CostCodeIn, user: User = Depends(CATALOG), db: Session = Depends(get_db)):
    if db.scalar(org_scoped(CostCode, user).where(CostCode.code == body.code)):
        raise _dup("Cost code already exists")
    c = CostCode(organization_id=user.organization_id, **body.model_dump())
    db.add(c)
    db.commit()
    return c


@router.get("/cost-codes", response_model=list[CostCodeOut])
def list_cost_codes(user: User = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(org_scoped(CostCode, user).order_by(CostCode.code)).all()


@router.post("/units", response_model=UnitOut, status_code=201)
def create_unit(body: UnitIn, user: User = Depends(CATALOG), db: Session = Depends(get_db)):
    if db.scalar(org_scoped(Unit, user).where(Unit.code == body.code)):
        raise _dup("Unit already exists")
    u = Unit(organization_id=user.organization_id, **body.model_dump())
    db.add(u)
    db.commit()
    return u


@router.get("/units", response_model=list[UnitOut])
def list_units(user: User = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(org_scoped(Unit, user).order_by(Unit.code)).all()


@router.post("/unit-conversions", response_model=ConversionOut, status_code=201)
def create_conversion(body: ConversionIn, user: User = Depends(CATALOG), db: Session = Depends(get_db)):
    get_owned(db, Unit, body.from_unit_id, user, code=422)
    get_owned(db, Unit, body.to_unit_id, user, code=422)
    if db.scalar(org_scoped(UnitConversion, user).where(UnitConversion.from_unit_id == body.from_unit_id,
                                                        UnitConversion.to_unit_id == body.to_unit_id)):
        raise _dup("Conversion already defined")
    c = UnitConversion(organization_id=user.organization_id, **body.model_dump())
    db.add(c)
    db.commit()
    return c


@router.get("/unit-conversions", response_model=list[ConversionOut])
def list_conversions(user: User = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(org_scoped(UnitConversion, user)).all()


# ---- BOQ
def _items(db: Session, boq: BOQ) -> list[BOQItem]:
    return list(db.scalars(select(BOQItem).where(BOQItem.boq_id == boq.id,
                                                 BOQItem.organization_id == boq.organization_id)
                           .order_by(BOQItem.item_code)))


def _item_out(i: BOQItem) -> ItemOut:
    rate = calc.unit_rate(i.material_rate, i.waste_pct, i.labour_rate, i.equipment_rate)
    return ItemOut(id=i.id, item_code=i.item_code, trade=i.trade, description=i.description, quantity=i.quantity,
                   unit_id=i.unit_id, waste_pct=i.waste_pct, material_rate=i.material_rate,
                   labour_rate=i.labour_rate, equipment_rate=i.equipment_rate, cost_code_id=i.cost_code_id,
                   unit_rate=rate, amount=calc.item_amount(i.quantity, rate))


def _boq_out(db: Session, boq: BOQ) -> BOQOut:
    items = _items(db, boq)
    s = calc.summarize(items, boq.overhead_pct, boq.contingency_pct, boq.profit_pct)
    return BOQOut(id=boq.id, project_id=boq.project_id, name=boq.name, status=boq.status,
                  overhead_pct=boq.overhead_pct, contingency_pct=boq.contingency_pct, profit_pct=boq.profit_pct,
                  items=[_item_out(i) for i in items], summary=SummaryOut(**s))


def _draft(boq: BOQ):
    if boq.status != ApprovalStatus.DRAFT:
        raise HTTPException(409, "Approved BOQs are read-only")


def _check_item_refs(db, user, unit_id=None, cost_code_id=None):
    if unit_id:
        get_owned(db, Unit, unit_id, user, code=422)
    if cost_code_id:
        get_owned(db, CostCode, cost_code_id, user, code=422)


@router.post("/boqs", response_model=BOQOut, status_code=201)
def create_boq(body: BOQIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    project = get_owned(db, Project, body.project_id, user, code=422)
    boq = BOQ(organization_id=user.organization_id, created_by=user.id, **body.model_dump())
    db.add(boq)
    db.commit()
    log_action(db, action="boq.create", org_id=user.organization_id, user_id=user.id, entity="boq",
               entity_id=boq.id, request=request, detail={"project": str(project.id)})
    return _boq_out(db, boq)


@router.get("/boqs", response_model=list[uuid.UUID])
def list_boq_ids(project_id: uuid.UUID | None = None, user: User = Depends(READ), db: Session = Depends(get_db)):
    q = org_scoped(BOQ, user)
    if project_id:
        q = q.where(BOQ.project_id == project_id)
    return [b.id for b in db.scalars(q.order_by(BOQ.created_at))]


@router.get("/boqs/{boq_id}", response_model=BOQOut)
def get_boq(boq_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    return _boq_out(db, get_owned(db, BOQ, boq_id, user))


@router.patch("/boqs/{boq_id}", response_model=BOQOut)
def update_boq(boq_id: uuid.UUID, body: BOQUpdate, request: Request, user: User = Depends(MANAGE),
               db: Session = Depends(get_db)):
    boq = get_owned(db, BOQ, boq_id, user)
    _draft(boq)
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(boq, k, v)
    db.commit()
    log_action(db, action="boq.update", org_id=user.organization_id, user_id=user.id, entity="boq",
               entity_id=boq.id, request=request)
    return _boq_out(db, boq)


@router.post("/boqs/{boq_id}/items", response_model=ItemOut, status_code=201)
def add_item(boq_id: uuid.UUID, body: ItemIn, request: Request, user: User = Depends(MANAGE),
             db: Session = Depends(get_db)):
    boq = get_owned(db, BOQ, boq_id, user)
    _draft(boq)
    _check_item_refs(db, user, body.unit_id, body.cost_code_id)
    item = BOQItem(organization_id=user.organization_id, boq_id=boq.id, **body.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _dup("Item code already exists in this BOQ")
    log_action(db, action="boq.item.create", org_id=user.organization_id, user_id=user.id, entity="boq_item",
               entity_id=item.id, request=request)
    return _item_out(item)


@router.patch("/boqs/{boq_id}/items/{item_id}", response_model=ItemOut)
def update_item(boq_id: uuid.UUID, item_id: uuid.UUID, body: ItemUpdate, request: Request,
                user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    boq = get_owned(db, BOQ, boq_id, user)
    _draft(boq)
    item = get_owned(db, BOQItem, item_id, user)
    if item.boq_id != boq.id:
        raise HTTPException(404, "BOQItem not found")
    data = body.model_dump(exclude_unset=True)
    _check_item_refs(db, user, data.get("unit_id"), data.get("cost_code_id"))
    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    log_action(db, action="boq.item.update", org_id=user.organization_id, user_id=user.id, entity="boq_item",
               entity_id=item.id, request=request, detail={"fields": list(data)})
    return _item_out(item)


@router.delete("/boqs/{boq_id}/items/{item_id}", status_code=204)
def delete_item(boq_id: uuid.UUID, item_id: uuid.UUID, request: Request, user: User = Depends(MANAGE),
                db: Session = Depends(get_db)):
    boq = get_owned(db, BOQ, boq_id, user)
    _draft(boq)
    item = get_owned(db, BOQItem, item_id, user)
    if item.boq_id != boq.id:
        raise HTTPException(404, "BOQItem not found")
    db.delete(item)
    db.commit()
    log_action(db, action="boq.item.delete", org_id=user.organization_id, user_id=user.id, entity="boq_item",
               entity_id=item_id, request=request)


@router.post("/boqs/{boq_id}/calculate", response_model=SummaryOut)
def calculate(boq_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    boq = get_owned(db, BOQ, boq_id, user)
    return SummaryOut(**calc.summarize(_items(db, boq), boq.overhead_pct, boq.contingency_pct, boq.profit_pct))


@router.post("/boqs/{boq_id}/approve", response_model=BOQOut)
def approve_boq(boq_id: uuid.UUID, request: Request, user: User = Depends(APPROVE), db: Session = Depends(get_db)):
    boq = get_owned(db, BOQ, boq_id, user)
    _draft(boq)
    if not _items(db, boq):
        raise HTTPException(422, "Cannot approve an empty BOQ")
    boq.status = ApprovalStatus.APPROVED
    db.commit()
    log_action(db, action="boq.approve", org_id=user.organization_id, user_id=user.id, entity="boq",
               entity_id=boq.id, request=request)
    return _boq_out(db, boq)
