"""Purchase orders (approval limits + budget commitment) and goods receipts (stock + actual cost)."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.boq.calculations import q2
from app.budgets import service as budget_service
from app.db import get_db
from app.deps import get_owned, org_scoped, require_permission
from app.inventory import service as stock_service
from app.inventory.models import InventoryItem, Warehouse
from app.inventory.models import MovementType as MT
from app.models import User
from app.procurement.models import (GoodsReceipt, GRNLine, POLine, POStatus, PurchaseOrder, PurchaseRequisition,
                                    QuoteLine, ReqStatus, RequisitionLine, Supplier, SupplierQuote)
from app.procurement.schemas import (Decision, GRNIn, GRNLineOut, GRNOut, POFromQuote, POIn, POLineOut, POOut, RejectIn)
from app.projects.models import Project

router = APIRouter(tags=["purchase-orders"])
READ = require_permission("procurement.read")
MANAGE = require_permission("procurement.manage")
APPROVE = require_permission("procurement.approve")
GRN = require_permission("grn.create")
OPEN_PO = (POStatus.APPROVED, POStatus.PARTIALLY_RECEIVED)


def _po_lines(db, po) -> list[POLine]:
    return list(db.scalars(select(POLine).where(POLine.po_id == po.id, POLine.organization_id == po.organization_id)
                           .order_by(POLine.created_at)))


def _po_out(db, po) -> POOut:
    return POOut(id=po.id, number=po.number, project_id=po.project_id, warehouse_id=po.warehouse_id,
                 supplier_id=po.supplier_id, requisition_id=po.requisition_id, status=po.status,
                 total_amount=po.total_amount, decision_comment=po.decision_comment,
                 lines=[POLineOut(id=l.id, item_id=l.item_id, quantity=l.quantity, unit_rate=l.unit_rate,
                                  received_qty=l.received_qty, amount=q2(l.quantity * l.unit_rate))
                        for l in _po_lines(db, po)])


def _cost_amounts(db, user, lines: list[POLine], qty_attr="quantity"):
    pairs = []
    for l in lines:
        item = db.get(InventoryItem, l.item_id)
        if not item.cost_code_id:
            raise HTTPException(422, f"Item {item.code} has no cost code; every cost must map to a budget line")
        pairs.append((item.cost_code_id, q2(getattr(l, qty_attr) * l.unit_rate)))
    return budget_service.group(pairs)


def _new_po(db, user, *, project, warehouse, supplier, lines: list[tuple], requisition_id=None, quote_id=None):
    po = PurchaseOrder(organization_id=user.organization_id, number=stock_service.next_number(
        db, PurchaseOrder, user.organization_id, "PO"), project_id=project.id, warehouse_id=warehouse.id,
        supplier_id=supplier.id, requisition_id=requisition_id, quote_id=quote_id, created_by=user.id)
    db.add(po)
    db.flush()
    total = Decimal("0")
    for item_id, qty, rate, req_line_id in lines:
        db.add(POLine(organization_id=user.organization_id, po_id=po.id, item_id=item_id, quantity=qty,
                      unit_rate=rate, requisition_line_id=req_line_id))
        total += q2(qty * rate)
    po.total_amount = total
    return po


@router.post("/purchase-orders/from-quote", response_model=POOut, status_code=201)
def po_from_quote(body: POFromQuote, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    quote = get_owned(db, SupplierQuote, body.quote_id, user, code=422)
    req = db.get(PurchaseRequisition, quote.requisition_id)
    if req.status != ReqStatus.APPROVED:
        raise HTTPException(409, f"Requisition is {req.status.value}; it must be APPROVED")
    supplier = db.get(Supplier, quote.supplier_id)
    if not supplier.is_approved:
        raise HTTPException(409, "Supplier is not approved")
    if db.scalar(select(PurchaseOrder).where(PurchaseOrder.requisition_id == req.id,
                                             PurchaseOrder.status.notin_([POStatus.CANCELLED, POStatus.REJECTED]))):
        raise HTTPException(409, "A purchase order already exists for this requisition")
    rates = {q.requisition_line_id: q.unit_rate for q in db.scalars(select(QuoteLine).where(QuoteLine.quote_id == quote.id))}
    lines = []
    for rl in db.scalars(select(RequisitionLine).where(RequisitionLine.requisition_id == req.id)
                         .order_by(RequisitionLine.created_at)):
        if rl.shortage_qty <= 0:
            continue
        if rl.id not in rates:
            raise HTTPException(422, "Quote does not cover every line that needs purchasing")
        lines.append((rl.item_id, rl.shortage_qty, rates[rl.id], rl.id))   # buy only the shortage
    if not lines:
        raise HTTPException(409, "Nothing to purchase: stock is sufficient")
    po = _new_po(db, user, project=db.get(Project, req.project_id), warehouse=db.get(Warehouse, req.warehouse_id),
                 supplier=supplier, lines=lines, requisition_id=req.id, quote_id=quote.id)
    req.status = ReqStatus.ORDERED
    db.commit()
    log_action(db, action="po.create", org_id=user.organization_id, user_id=user.id, entity="purchase_order",
               entity_id=po.id, request=request, detail={"from_quote": str(quote.id)})
    return _po_out(db, po)


@router.post("/purchase-orders", response_model=POOut, status_code=201)
def create_po(body: POIn, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    project = get_owned(db, Project, body.project_id, user, code=422)
    wh = get_owned(db, Warehouse, body.warehouse_id, user, code=422)
    if wh.project_id and wh.project_id != project.id:
        raise HTTPException(422, "This warehouse belongs to a different project")
    supplier = get_owned(db, Supplier, body.supplier_id, user, code=422)
    for l in body.lines:
        get_owned(db, InventoryItem, l.item_id, user, code=422)
    po = _new_po(db, user, project=project, warehouse=wh, supplier=supplier,
                 lines=[(l.item_id, l.quantity, l.unit_rate, None) for l in body.lines])
    db.commit()
    log_action(db, action="po.create", org_id=user.organization_id, user_id=user.id, entity="purchase_order",
               entity_id=po.id, request=request)
    return _po_out(db, po)


@router.get("/purchase-orders", response_model=list[POOut])
def list_pos(project_id: uuid.UUID | None = None, status: POStatus | None = None, limit: int = 100,
             user: User = Depends(READ), db: Session = Depends(get_db)):
    q = org_scoped(PurchaseOrder, user)
    if project_id:
        q = q.where(PurchaseOrder.project_id == project_id)
    if status:
        q = q.where(PurchaseOrder.status == status)
    return [_po_out(db, p) for p in db.scalars(q.order_by(PurchaseOrder.created_at.desc()).limit(min(limit, 200)))]


@router.get("/purchase-orders/{po_id}", response_model=POOut)
def get_po(po_id: uuid.UUID, user: User = Depends(READ), db: Session = Depends(get_db)):
    return _po_out(db, get_owned(db, PurchaseOrder, po_id, user))


def _expect(po, *allowed):
    if po.status not in allowed:
        raise HTTPException(409, f"PO is {po.status.value}; expected {' or '.join(a.value for a in allowed)}")


@router.post("/purchase-orders/{po_id}/submit", response_model=POOut)
def submit_po(po_id: uuid.UUID, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    po = get_owned(db, PurchaseOrder, po_id, user)
    _expect(po, POStatus.DRAFT)
    po.status = POStatus.PENDING_APPROVAL
    db.commit()
    log_action(db, action="po.submit", org_id=user.organization_id, user_id=user.id, entity="purchase_order",
               entity_id=po.id, request=request, detail={"total": str(po.total_amount)})
    return _po_out(db, po)


@router.post("/purchase-orders/{po_id}/approve", response_model=POOut)
def approve_po(po_id: uuid.UUID, body: Decision, request: Request, user: User = Depends(APPROVE),
               db: Session = Depends(get_db)):
    po = get_owned(db, PurchaseOrder, po_id, user)
    _expect(po, POStatus.PENDING_APPROVAL)
    if po.total_amount > user.role.approval_limit:
        raise HTTPException(403, f"PO total {po.total_amount} exceeds your approval limit "
                                 f"({user.role.approval_limit}); it needs a higher approver")
    if not db.get(Supplier, po.supplier_id).is_approved:
        raise HTTPException(409, "Supplier is not approved")
    try:
        budget_service.commit(db, user.organization_id, po.project_id, _cost_amounts(db, user, _po_lines(db, po)))
    except HTTPException:
        db.rollback()
        raise
    po.status, po.decided_by, po.decided_at, po.decision_comment = (POStatus.APPROVED, user.id,
                                                                    datetime.now(timezone.utc), body.comment)
    db.commit()
    log_action(db, action="po.approve", org_id=user.organization_id, user_id=user.id, entity="purchase_order",
               entity_id=po.id, request=request, detail={"total": str(po.total_amount)})
    return _po_out(db, po)


def _reopen_requisition(db, po):
    if po.requisition_id:
        req = db.get(PurchaseRequisition, po.requisition_id)
        if req.status == ReqStatus.ORDERED:
            req.status = ReqStatus.APPROVED


@router.post("/purchase-orders/{po_id}/reject", response_model=POOut)
def reject_po(po_id: uuid.UUID, body: RejectIn, request: Request, user: User = Depends(APPROVE),
              db: Session = Depends(get_db)):
    po = get_owned(db, PurchaseOrder, po_id, user)
    _expect(po, POStatus.PENDING_APPROVAL)
    po.status, po.decided_by, po.decided_at, po.decision_comment = (POStatus.REJECTED, user.id,
                                                                    datetime.now(timezone.utc), body.comment)
    _reopen_requisition(db, po)
    db.commit()
    log_action(db, action="po.reject", org_id=user.organization_id, user_id=user.id, entity="purchase_order",
               entity_id=po.id, request=request)
    return _po_out(db, po)


@router.post("/purchase-orders/{po_id}/cancel", response_model=POOut)
def cancel_po(po_id: uuid.UUID, request: Request, user: User = Depends(MANAGE), db: Session = Depends(get_db)):
    po = get_owned(db, PurchaseOrder, po_id, user)
    _expect(po, POStatus.DRAFT, POStatus.PENDING_APPROVAL, POStatus.APPROVED)
    if po.status == POStatus.APPROVED:
        if "procurement.approve" not in {p.code for p in user.role.permissions}:
            raise HTTPException(403, "Cancelling an approved PO needs an approver")
        lines = _po_lines(db, po)
        if any(l.received_qty > 0 for l in lines):
            raise HTTPException(409, "PO already has receipts and cannot be cancelled")
        budget_service.release(db, user.organization_id, po.project_id, _cost_amounts(db, user, lines))
    po.status = POStatus.CANCELLED
    _reopen_requisition(db, po)
    db.commit()
    log_action(db, action="po.cancel", org_id=user.organization_id, user_id=user.id, entity="purchase_order",
               entity_id=po.id, request=request)
    return _po_out(db, po)


# ---- goods receipts
def _grn_out(db, grn, po) -> GRNOut:
    ls = db.scalars(select(GRNLine).where(GRNLine.grn_id == grn.id))
    return GRNOut(id=grn.id, number=grn.number, po_id=grn.po_id, warehouse_id=grn.warehouse_id,
                  delivery_note=grn.delivery_note, po_status=po.status,
                  lines=[GRNLineOut.model_validate(l) for l in ls])


@router.post("/goods-receipts", response_model=GRNOut, status_code=201)
def create_grn(body: GRNIn, request: Request, user: User = Depends(GRN), db: Session = Depends(get_db)):
    po = get_owned(db, PurchaseOrder, body.po_id, user, code=422)
    if po.status not in OPEN_PO:
        raise HTTPException(409, f"PO is {po.status.value}; goods can only be received against an approved PO")
    po_lines = {l.id: l for l in _po_lines(db, po)}
    ids = [l.po_line_id for l in body.lines]
    if len(set(ids)) != len(ids) or any(i not in po_lines for i in ids):
        raise HTTPException(422, "Lines must be unique and belong to this PO")
    try:
        grn = GoodsReceipt(organization_id=user.organization_id, number=stock_service.next_number(
            db, GoodsReceipt, user.organization_id, "GRN"), po_id=po.id, warehouse_id=po.warehouse_id,
            delivery_note=body.delivery_note, notes=body.notes, received_by=user.id)
        db.add(grn)
        db.flush()
        actual_pairs = []
        for l in body.lines:
            pl = po_lines[l.po_line_id]
            if l.quantity_accepted + l.quantity_rejected <= 0:
                raise HTTPException(422, "Each line needs an accepted or rejected quantity")
            remaining = pl.quantity - pl.received_qty
            if l.quantity_accepted + l.quantity_rejected > remaining:
                raise HTTPException(409, f"Delivery exceeds the outstanding PO quantity ({remaining})")
            item = db.get(InventoryItem, pl.item_id)
            db.add(GRNLine(organization_id=user.organization_id, grn_id=grn.id, po_line_id=pl.id, item_id=pl.item_id,
                           quantity_accepted=l.quantity_accepted, quantity_rejected=l.quantity_rejected,
                           unit_rate=pl.unit_rate))
            if l.quantity_accepted > 0:
                stock_service.post_transaction(
                    db, org_id=user.organization_id, user_id=user.id, warehouse_id=po.warehouse_id,
                    item_id=pl.item_id, mtype=MT.PURCHASE_RECEIPT, qty=l.quantity_accepted, unit_cost=pl.unit_rate,
                    project_id=po.project_id, cost_code_id=item.cost_code_id, ref_type="GRN", ref_id=grn.number,
                    note=f"PO {po.number}")
                pl.received_qty += l.quantity_accepted
                actual_pairs.append((item.cost_code_id, q2(l.quantity_accepted * pl.unit_rate)))
        budget_service.record_actual(db, user.organization_id, po.project_id, budget_service.group(actual_pairs))
        po.status = (POStatus.RECEIVED if all(l.received_qty >= l.quantity for l in po_lines.values())
                     else POStatus.PARTIALLY_RECEIVED)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    log_action(db, action="grn.create", org_id=user.organization_id, user_id=user.id, entity="goods_receipt",
               entity_id=grn.id, request=request, detail={"po": po.number, "number": grn.number})
    return _grn_out(db, grn, po)


@router.get("/goods-receipts", response_model=list[GRNOut])
def list_grns(po_id: uuid.UUID | None = None, user: User = Depends(READ), db: Session = Depends(get_db)):
    q = org_scoped(GoodsReceipt, user)
    if po_id:
        q = q.where(GoodsReceipt.po_id == po_id)
    return [_grn_out(db, g, db.get(PurchaseOrder, g.po_id)) for g in db.scalars(q.order_by(GoodsReceipt.created_at))]
