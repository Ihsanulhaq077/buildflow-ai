"""Suppliers, requisitions (with stock + BOQ checks), quotes and quote comparison."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.boq.models import BOQ, ApprovalStatus, BOQItem
from app.config import settings
from app.db import get_db
from app.deps import get_owned, org_scoped, require_permission
from app.inventory.models import InventoryItem, StockBalance, Warehouse
from app.inventory.service import next_number
from app.models import User
from app.procurement.models import (POLine, POStatus, PurchaseOrder, PurchaseRequisition, QuoteLine, ReqStatus,
                                    RequisitionLine, Supplier, SupplierQuote)
from app.procurement.schemas import (Decision, QuoteIn, RejectIn, ReqIn, ReqLineOut, ReqOut, StockCheckOut,
                                     SupplierIn, SupplierOut)
from app.projects.models import Project

router = APIRouter(tags=["procurement"])
READ = require_permission("procurement.read")
MANAGE = require_permission("procurement.manage")
APPROVE = require_permission("procurement.approve")
SUP_APPROVE = require_permission("suppliers.approve")
CREATE_REQ = require_permission("requisitions.create")
OPEN_PO = (POStatus.APPROVED, POStatus.PARTIALLY_RECEIVED)


def stock_position(db: Session, org_id, warehouse_id, item_id) -> tuple[Decimal, Decimal]:
    on_hand = db.scalar(select(StockBalance.quantity).where(
        StockBalance.organization_id == org_id, StockBalance.warehouse_id == warehouse_id,
        StockBalance.item_id == item_id)) or Decimal("0")
    on_order = db.scalar(select(func.coalesce(func.sum(POLine.quantity - POLine.received_qty), 0))
                         .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
                         .where(PurchaseOrder.organization_id == org_id, PurchaseOrder.warehouse_id == warehouse_id,
                                POLine.item_id == item_id, PurchaseOrder.status.in_(OPEN_PO)))
    return Decimal(on_hand), Decimal(on_order or 0)


# ---- suppliers
@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(body: SupplierIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    if db.scalar(org_scoped(Supplier, user).where(Supplier.name == body.name)):
        raise HTTPException(409, "Supplier already exists")
    s = Supplier(organization_id=user.organization_id, **body.model_dump())
    db.add(s)
    db.commit()
    log_action(db, action="supplier.create", org_id=user.organization_id, user_id=user.id, entity="supplier",
               entity_id=s.id, request=request)
    return s


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(user: User = Depends(READ), db: Session = Depends(get_db)):
    return db.scalars(org_scoped(Supplier, user).order_by(Supplier.name)).all()


@router.post("/suppliers/{supplier_id}/approve", response_model=SupplierOut)
def approve_supplier(supplier_id: uuid.UUID, request: Request, user: User = Depends(SUP_APPROVE),
                     db: Session = Depends(get_db)):
    s = get_owned(db, Supplier, supplier_id, user)
    s.is_approved, s.approved_by, s.approved_at = True, user.id, datetime.now(timezone.utc)
    db.commit()
    log_action(db, action="supplier.approve", org_id=user.organization_id, user_id=user.id, entity="supplier",
               entity_id=s.id, request=request)
    return s


# ---- requisitions
def _lines(db, req) -> list[RequisitionLine]:
    return list(db.scalars(select(RequisitionLine).where(RequisitionLine.requisition_id == req.id,
                                                         RequisitionLine.organization_id == req.organization_id)
                           .order_by(RequisitionLine.created_at)))


def _req_out(db, req) -> ReqOut:
    return ReqOut(id=req.id, number=req.number, project_id=req.project_id, warehouse_id=req.warehouse_id,
                  status=req.status, notes=req.notes, requested_by=req.requested_by,
                  decision_comment=req.decision_comment,
                  lines=[ReqLineOut.model_validate(l) for l in _lines(db, req)])


def _refresh_checks(db, org_id, req, line: RequisitionLine):
    """Stock check + BOQ check. Shortage = requested - on hand - already on order."""
    on_hand, on_order = stock_position(db, org_id, req.warehouse_id, line.item_id)
    line.stock_on_hand, line.on_order = on_hand, on_order
    line.shortage_qty = max(line.quantity - on_hand - on_order, Decimal("0"))
    line.exceeds_boq = False
    if line.boq_item_id:
        bi = db.get(BOQItem, line.boq_item_id)
        item = db.get(InventoryItem, line.item_id)
        if bi and item and bi.unit_id == item.unit_id:  # only comparable when units match
            used = db.scalar(select(func.coalesce(func.sum(RequisitionLine.quantity), 0))
                             .join(PurchaseRequisition, PurchaseRequisition.id == RequisitionLine.requisition_id)
                             .where(RequisitionLine.organization_id == org_id,
                                    RequisitionLine.boq_item_id == bi.id, RequisitionLine.id != line.id,
                                    PurchaseRequisition.status.in_([ReqStatus.SUBMITTED, ReqStatus.APPROVED,
                                                                    ReqStatus.ORDERED])))
            allowed = bi.quantity * (1 + bi.waste_pct / 100)
            line.exceeds_boq = Decimal(used) + line.quantity > allowed


@router.get("/requisitions/stock-check", response_model=StockCheckOut)
def stock_check(warehouse_id: uuid.UUID, item_id: uuid.UUID, quantity: Decimal, user: User = Depends(READ),
                db: Session = Depends(get_db)):
    get_owned(db, Warehouse, warehouse_id, user)
    get_owned(db, InventoryItem, item_id, user)
    oh, oo = stock_position(db, user.organization_id, warehouse_id, item_id)
    return StockCheckOut(item_id=item_id, requested=quantity, stock_on_hand=oh, on_order=oo,
                         shortage_qty=max(quantity - oh - oo, Decimal("0")))


@router.post("/requisitions", response_model=ReqOut, status_code=201)
def create_requisition(body: ReqIn, request: Request, user: User = Depends(CREATE_REQ), db: Session = Depends(get_db)):
    project = get_owned(db, Project, body.project_id, user, code=422)
    wh = get_owned(db, Warehouse, body.warehouse_id, user, code=422)
    if wh.project_id and wh.project_id != project.id:
        raise HTTPException(422, "This warehouse belongs to a different project")
    req = PurchaseRequisition(organization_id=user.organization_id, number=next_number(
        db, PurchaseRequisition, user.organization_id, "REQ"), project_id=project.id, warehouse_id=wh.id,
        notes=body.notes, requested_by=user.id)
    db.add(req)
    db.flush()
    for l in body.lines:
        get_owned(db, InventoryItem, l.item_id, user, code=422)
        if l.boq_item_id:
            bi = get_owned(db, BOQItem, l.boq_item_id, user, code=422)
            boq = db.get(BOQ, bi.boq_id)
            if boq.project_id != project.id or boq.status != ApprovalStatus.APPROVED:
                raise HTTPException(422, "BOQ item must belong to an approved BOQ of this project")
        line = RequisitionLine(organization_id=user.organization_id, requisition_id=req.id, **l.model_dump())
        db.add(line)
        db.flush()
        _refresh_checks(db, user.organization_id, req, line)
    db.commit()
    log_action(db, action="requisition.create", org_id=user.organization_id, user_id=user.id,
               entity="requisition", entity_id=req.id, request=request)
    return _req_out(db, req)


@router.get("/requisitions", response_model=list[ReqOut])
def list_requisitions(project_id: uuid.UUID | None = None, status: ReqStatus | None = None, limit: int = 100,
                      user: User = Depends(READ), db: Session = Depends(get_db)):
    q = org_scoped(PurchaseRequisition, user)
    if project_id:
        q = q.where(PurchaseRequisition.project_id == project_id)
    if status:
        q = q.where(PurchaseRequisition.status == status)
    return [_req_out(db, r) for r in db.scalars(q.order_by(PurchaseRequisition.created_at.desc()).limit(min(limit, 200)))]


@router.get("/requisitions/{req_id}", response_model=ReqOut)
def get_requisition(req_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    return _req_out(db, get_owned(db, PurchaseRequisition, req_id, user))


def _expect(req, *allowed: ReqStatus):
    if req.status not in allowed:
        raise HTTPException(409, f"Requisition is {req.status.value}; expected {' or '.join(a.value for a in allowed)}")


@router.post("/requisitions/{req_id}/submit", response_model=ReqOut)
def submit_requisition(req_id: uuid.UUID, request: Request, user: User = Depends(CREATE_REQ), db: Session = Depends(get_db)):
    req = get_owned(db, PurchaseRequisition, req_id, user)
    _expect(req, ReqStatus.DRAFT)
    lines = _lines(db, req)
    for l in lines:
        _refresh_checks(db, user.organization_id, req, l)   # re-check against live stock
    if all(l.shortage_qty == 0 for l in lines):
        db.commit()
        raise HTTPException(409, "Stock is sufficient (on hand + on order). Issue from stock instead of buying.")
    req.status = ReqStatus.SUBMITTED
    db.commit()
    log_action(db, action="requisition.submit", org_id=user.organization_id, user_id=user.id,
               entity="requisition", entity_id=req.id, request=request)
    return _req_out(db, req)


@router.post("/requisitions/{req_id}/approve", response_model=ReqOut)
def approve_requisition(req_id: uuid.UUID, body: Decision, request: Request, user: User = Depends(APPROVE),
                        db: Session = Depends(get_db)):
    req = get_owned(db, PurchaseRequisition, req_id, user)
    _expect(req, ReqStatus.SUBMITTED)
    req.status, req.decided_by, req.decision_comment = ReqStatus.APPROVED, user.id, body.comment
    db.commit()
    log_action(db, action="requisition.approve", org_id=user.organization_id, user_id=user.id,
               entity="requisition", entity_id=req.id, request=request)
    return _req_out(db, req)


@router.post("/requisitions/{req_id}/reject", response_model=ReqOut)
def reject_requisition(req_id: uuid.UUID, body: RejectIn, request: Request, user: User = Depends(APPROVE),
                       db: Session = Depends(get_db)):
    req = get_owned(db, PurchaseRequisition, req_id, user)
    _expect(req, ReqStatus.SUBMITTED)
    req.status, req.decided_by, req.decision_comment = ReqStatus.REJECTED, user.id, body.comment
    db.commit()
    log_action(db, action="requisition.reject", org_id=user.organization_id, user_id=user.id,
               entity="requisition", entity_id=req.id, request=request)
    return _req_out(db, req)


@router.post("/requisitions/{req_id}/cancel", response_model=ReqOut)
def cancel_requisition(req_id: uuid.UUID, request: Request, user: User = Depends(CREATE_REQ), db: Session = Depends(get_db)):
    req = get_owned(db, PurchaseRequisition, req_id, user)
    _expect(req, ReqStatus.DRAFT, ReqStatus.SUBMITTED, ReqStatus.APPROVED)
    if req.requested_by != user.id and "procurement.approve" not in {p.code for p in user.role.permissions}:
        raise HTTPException(403, "Only the requester or an approver can cancel")
    req.status = ReqStatus.CANCELLED
    db.commit()
    log_action(db, action="requisition.cancel", org_id=user.organization_id, user_id=user.id,
               entity="requisition", entity_id=req.id, request=request)
    return _req_out(db, req)


# ---- quotes & comparison
@router.post("/requisitions/{req_id}/quotes", status_code=201)
def add_quote(req_id: uuid.UUID, body: QuoteIn, request: Request, user: User = Depends(MANAGE),
              db: Session = Depends(get_db)):
    req = get_owned(db, PurchaseRequisition, req_id, user)
    _expect(req, ReqStatus.APPROVED)
    sup = get_owned(db, Supplier, body.supplier_id, user, code=422)
    if db.scalar(select(SupplierQuote).where(SupplierQuote.requisition_id == req.id,
                                             SupplierQuote.supplier_id == sup.id)):
        raise HTTPException(409, "This supplier already quoted for this requisition")
    valid = {l.id for l in _lines(db, req)}
    if any(l.requisition_line_id not in valid for l in body.lines):
        raise HTTPException(422, "Quote line does not belong to this requisition")
    if len({l.requisition_line_id for l in body.lines}) != len(body.lines):
        raise HTTPException(422, "Duplicate requisition line in quote")
    q = SupplierQuote(organization_id=user.organization_id, requisition_id=req.id, supplier_id=sup.id,
                      valid_until=body.valid_until, notes=body.notes, created_by=user.id)
    db.add(q)
    db.flush()
    for l in body.lines:
        db.add(QuoteLine(organization_id=user.organization_id, quote_id=q.id,
                         requisition_line_id=l.requisition_line_id, unit_rate=l.unit_rate))
    db.commit()
    log_action(db, action="quote.create", org_id=user.organization_id, user_id=user.id, entity="quote",
               entity_id=q.id, request=request)
    return {"id": str(q.id), "supplier_id": str(sup.id), "lines": len(body.lines)}


@router.get("/requisitions/{req_id}/comparison")
def comparison(req_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    req = get_owned(db, PurchaseRequisition, req_id, user)
    lines = [l for l in _lines(db, req) if l.shortage_qty > 0]
    quotes = list(db.scalars(select(SupplierQuote).where(SupplierQuote.requisition_id == req.id)))
    sup = {s.id: s for s in db.scalars(org_scoped(Supplier, user))}
    rates: dict[tuple, Decimal] = {}
    for ql in db.scalars(select(QuoteLine).where(QuoteLine.quote_id.in_([q.id for q in quotes] or [None]))):
        rates[(ql.quote_id, ql.requisition_line_id)] = ql.unit_rate
    pct = Decimal(str(settings.price_anomaly_pct))
    out_lines, totals = [], {q.id: Decimal("0") for q in quotes}
    covers = {q.id: True for q in quotes}
    for l in lines:
        last = db.scalar(select(POLine.unit_rate).join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
                         .where(PurchaseOrder.organization_id == user.organization_id, POLine.item_id == l.item_id,
                                PurchaseOrder.status.in_([POStatus.APPROVED, POStatus.PARTIALLY_RECEIVED,
                                                          POStatus.RECEIVED]))
                         .order_by(PurchaseOrder.decided_at.desc()).limit(1))
        row = [(q, rates[(q.id, l.id)]) for q in quotes if (q.id, l.id) in rates]
        low = min((r for _, r in row), default=None)
        for q in quotes:
            if (q.id, l.id) in rates:
                totals[q.id] += (l.shortage_qty * rates[(q.id, l.id)]).quantize(Decimal("0.01"))
            else:
                covers[q.id] = False
        out_lines.append({
            "requisition_line_id": str(l.id), "item_id": str(l.item_id), "shortage_qty": str(l.shortage_qty),
            "last_purchase_rate": str(last) if last is not None else None,
            "quotes": [{"quote_id": str(q.id), "supplier_id": str(q.supplier_id), "supplier": sup[q.supplier_id].name,
                        "unit_rate": str(r), "is_lowest": r == low,
                        "price_anomaly": bool(last is not None and r > last * (1 + pct / 100))} for q, r in row]})
    complete = {q.id: totals[q.id] for q in quotes if covers[q.id]}
    best = min(complete.values(), default=None)
    return {"requisition_id": str(req.id), "anomaly_threshold_pct": str(pct), "lines": out_lines,
            "suppliers": [{"quote_id": str(q.id), "supplier_id": str(q.supplier_id), "supplier": sup[q.supplier_id].name,
                           "covers_all_lines": covers[q.id], "supplier_approved": sup[q.supplier_id].is_approved,
                           "total": str(totals[q.id]) if covers[q.id] else None,
                           "is_lowest_total": covers[q.id] and totals[q.id] == best} for q in quotes]}
