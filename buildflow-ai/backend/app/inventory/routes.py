import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.boq.models import CostCode, Unit
from app.db import get_db
from app.deps import get_owned, org_scoped, require_permission
from app.inventory import service
from app.inventory.models import (InventoryItem, MaterialIssue, MaterialIssueLine, MovementType, StockBalance,
                                  StockTransaction, Warehouse)
from app.inventory.models import MovementType as MT
from app.inventory.schemas import (AdjustIn, ConsumptionOut, ItemIn, ItemOut, MovementIn, MovementLineOut,
                                   MovementOut, StockOut, TransferIn, TxOut, WarehouseIn, WarehouseOut)
from app.models import User
from app.projects.models import Project

router = APIRouter(tags=["inventory"])
READ = require_permission("inventory.read")
MANAGE = require_permission("inventory.manage")
ISSUE = require_permission("inventory.issue")
ADJUST = require_permission("inventory.adjust")


def _project_store_rule(wh: Warehouse, project_id):
    if wh.project_id and wh.project_id != project_id:
        raise HTTPException(422, "This warehouse belongs to a different project")


@router.post("/warehouses", response_model=WarehouseOut, status_code=201)
def create_warehouse(body: WarehouseIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    if body.project_id:
        get_owned(db, Project, body.project_id, user, code=422)
    if db.scalar(org_scoped(Warehouse, user).where(Warehouse.name == body.name)):
        raise HTTPException(409, "Warehouse name already exists")
    w = Warehouse(organization_id=user.organization_id, **body.model_dump())
    db.add(w)
    db.commit()
    log_action(db, action="warehouse.create", org_id=user.organization_id, user_id=user.id, entity="warehouse",
               entity_id=w.id, request=request)
    return w


@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(user: User = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(org_scoped(Warehouse, user).order_by(Warehouse.name)).all()


@router.post("/inventory/items", response_model=ItemOut, status_code=201)
def create_item(body: ItemIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    get_owned(db, Unit, body.unit_id, user, code=422)
    if body.cost_code_id:
        get_owned(db, CostCode, body.cost_code_id, user, code=422)
    if db.scalar(org_scoped(InventoryItem, user).where(InventoryItem.code == body.code)):
        raise HTTPException(409, "Item code already exists")
    i = InventoryItem(organization_id=user.organization_id, **body.model_dump())
    db.add(i)
    db.commit()
    log_action(db, action="inventory.item.create", org_id=user.organization_id, user_id=user.id,
               entity="inventory_item", entity_id=i.id, request=request)
    return i


@router.get("/inventory/items", response_model=list[ItemOut])
def list_items(user: User = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(org_scoped(InventoryItem, user).order_by(InventoryItem.code)).all()


@router.get("/inventory/stock", response_model=list[StockOut])
def stock(warehouse_id: uuid.UUID | None = None, item_id: uuid.UUID | None = None,
          user: User = Depends(READ), db: Session = Depends(get_db)):
    q = org_scoped(StockBalance, user)
    if warehouse_id:
        q = q.where(StockBalance.warehouse_id == warehouse_id)
    if item_id:
        q = q.where(StockBalance.item_id == item_id)
    items = {i.id: i for i in db.scalars(org_scoped(InventoryItem, user))}
    out = []
    for b in db.scalars(q):
        it = items[b.item_id]
        out.append(StockOut(warehouse_id=b.warehouse_id, item_id=b.item_id, item_code=it.code, item_name=it.name,
                            quantity=b.quantity, avg_cost=b.avg_cost, value=(b.quantity * b.avg_cost).quantize(Decimal("0.01")),
                            reorder_level=it.reorder_level,
                            below_reorder=bool(it.reorder_level) and b.quantity <= it.reorder_level))
    return sorted(out, key=lambda s: (s.item_code, str(s.warehouse_id)))


@router.get("/inventory/transactions", response_model=list[TxOut])
def transactions(warehouse_id: uuid.UUID | None = None, item_id: uuid.UUID | None = None,
                 project_id: uuid.UUID | None = None, limit: int = 200, user: User = Depends(READ),
                 db: Session = Depends(get_db)):
    q = org_scoped(StockTransaction, user)
    for col, val in ((StockTransaction.warehouse_id, warehouse_id), (StockTransaction.item_id, item_id),
                     (StockTransaction.project_id, project_id)):
        if val:
            q = q.where(col == val)
    return db.scalars(q.order_by(StockTransaction.created_at.desc()).limit(min(limit, 1000))).all()


def _movement(db, user, body: MovementIn, kind: str, request) -> MovementOut:
    wh = get_owned(db, Warehouse, body.warehouse_id, user, code=422)
    project = get_owned(db, Project, body.project_id, user, code=422)
    _project_store_rule(wh, project.id)
    mtype = MT.MATERIAL_ISSUE if kind == "ISSUE" else MT.MATERIAL_RETURN
    header = MaterialIssue(organization_id=user.organization_id, number=service.next_number(
        db, MaterialIssue, user.organization_id, "ISS" if kind == "ISSUE" else "RET"),
        kind=kind, warehouse_id=wh.id, project_id=project.id, note=body.note, created_by=user.id)
    db.add(header)
    db.flush()
    lines = []
    for l in body.lines:
        item = get_owned(db, InventoryItem, l.item_id, user, code=422)
        tx = service.post_transaction(db, org_id=user.organization_id, user_id=user.id, warehouse_id=wh.id,
                                      item_id=item.id, mtype=mtype, qty=l.quantity, project_id=project.id,
                                      cost_code_id=item.cost_code_id, ref_type=kind, ref_id=header.number,
                                      note=body.note)
        db.add(MaterialIssueLine(organization_id=user.organization_id, issue_id=header.id, item_id=item.id,
                                 quantity=l.quantity, unit_cost=tx.unit_cost))
        lines.append(MovementLineOut(item_id=item.id, quantity=l.quantity, unit_cost=tx.unit_cost))
    db.commit()
    log_action(db, action=f"inventory.{kind.lower()}", org_id=user.organization_id, user_id=user.id,
               entity="material_issue", entity_id=header.id, request=request, detail={"number": header.number})
    return MovementOut(id=header.id, number=header.number, kind=kind, warehouse_id=wh.id, project_id=project.id, lines=lines)


@router.post("/inventory/issues", response_model=MovementOut, status_code=201)
def issue(body: MovementIn, request: Request, user: User = Depends(ISSUE), db: Session = Depends(get_db)):
    try:
        return _movement(db, user, body, "ISSUE", request)
    except HTTPException:
        db.rollback()
        raise


@router.post("/inventory/returns", response_model=MovementOut, status_code=201)
def material_return(body: MovementIn, request: Request, user: User = Depends(ISSUE), db: Session = Depends(get_db)):
    try:
        return _movement(db, user, body, "RETURN", request)
    except HTTPException:
        db.rollback()
        raise


@router.post("/inventory/transfers", status_code=201)
def transfer(body: TransferIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    src = get_owned(db, Warehouse, body.from_warehouse_id, user, code=422)
    dst = get_owned(db, Warehouse, body.to_warehouse_id, user, code=422)
    ref = service.next_number(db, StockTransaction, user.organization_id, "TRF")
    try:
        for l in body.lines:
            item = get_owned(db, InventoryItem, l.item_id, user, code=422)
            out = service.post_transaction(db, org_id=user.organization_id, user_id=user.id, warehouse_id=src.id,
                                           item_id=item.id, mtype=MT.TRANSFER_OUT, qty=l.quantity,
                                           ref_type="TRANSFER", ref_id=ref, note=body.note)
            service.post_transaction(db, org_id=user.organization_id, user_id=user.id, warehouse_id=dst.id,
                                     item_id=item.id, mtype=MT.TRANSFER_IN, qty=l.quantity, unit_cost=out.unit_cost,
                                     ref_type="TRANSFER", ref_id=ref, note=body.note)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    log_action(db, action="inventory.transfer", org_id=user.organization_id, user_id=user.id, entity="transfer",
               entity_id=ref, request=request)
    return {"reference": ref, "lines": len(body.lines)}


@router.post("/inventory/adjustments", status_code=201)
def adjust(body: AdjustIn, request: Request, user: User = Depends(ADJUST), db: Session = Depends(get_db)):
    wh = get_owned(db, Warehouse, body.warehouse_id, user, code=422)
    item = get_owned(db, InventoryItem, body.item_id, user, code=422)
    if body.project_id:
        get_owned(db, Project, body.project_id, user, code=422)
    mtype, inc = {"OPENING_STOCK": (MT.OPENING_STOCK, None), "INCREASE": (MT.ADJUSTMENT, True),
                  "DECREASE": (MT.ADJUSTMENT, False), "DAMAGE": (MT.DAMAGE, None), "WASTE": (MT.WASTE, None)}[body.kind]
    try:
        tx = service.post_transaction(db, org_id=user.organization_id, user_id=user.id, warehouse_id=wh.id,
                                      item_id=item.id, mtype=mtype, qty=body.quantity, unit_cost=body.unit_cost,
                                      increase=inc, project_id=body.project_id, cost_code_id=item.cost_code_id,
                                      ref_type="ADJUSTMENT", note=body.reason)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    log_action(db, action=f"inventory.{body.kind.lower()}", org_id=user.organization_id, user_id=user.id,
               entity="stock_transaction", entity_id=tx.id, request=request, detail={"reason": body.reason})
    return {"id": str(tx.id), "type": tx.type.value, "quantity": str(tx.quantity), "unit_cost": str(tx.unit_cost)}


@router.get("/inventory/consumption", response_model=list[ConsumptionOut])
def consumption(project_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    get_owned(db, Project, project_id, user)
    items = {i.id: i for i in db.scalars(org_scoped(InventoryItem, user))}
    agg = defaultdict(lambda: [Decimal("0"), Decimal("0"), Decimal("0")])  # issued, returned, net cost
    q = org_scoped(StockTransaction, user).where(StockTransaction.project_id == project_id,
                                                 StockTransaction.type.in_([MT.MATERIAL_ISSUE, MT.MATERIAL_RETURN]))
    for t in db.scalars(q):
        a = agg[t.item_id]
        if t.type == MT.MATERIAL_ISSUE:
            a[0] += -t.quantity
            a[2] += -t.quantity * t.unit_cost
        else:
            a[1] += t.quantity
            a[2] -= t.quantity * t.unit_cost
    return [ConsumptionOut(item_id=i, item_code=items[i].code, issued=a[0], returned=a[1], net_quantity=a[0] - a[1],
                           net_cost=a[2].quantize(Decimal("0.01"))) for i, a in sorted(agg.items(), key=lambda kv: items[kv[0]].code)]
