"""Stock posting. All quantity/cost arithmetic is deterministic Decimal; ledger rows are append-only."""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.inventory.models import MovementType as MT
from app.inventory.models import StockBalance, StockTransaction

IN_TYPES = {MT.OPENING_STOCK, MT.PURCHASE_RECEIPT, MT.MATERIAL_RETURN, MT.TRANSFER_IN}
OUT_TYPES = {MT.MATERIAL_ISSUE, MT.TRANSFER_OUT, MT.DAMAGE, MT.WASTE}
COST_REQUIRED = {MT.OPENING_STOCK, MT.PURCHASE_RECEIPT}


def q4(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def next_number(db: Session, model, org_id, prefix: str) -> str:
    n = db.scalar(select(func.count()).select_from(model).where(model.organization_id == org_id)) or 0
    return f"{prefix}-{n + 1:05d}"


def post_transaction(db: Session, *, org_id, user_id, warehouse_id, item_id, mtype: MT, qty: Decimal,
                     unit_cost: Decimal | None = None, increase: bool | None = None, project_id=None,
                     cost_code_id=None, ref_type: str = "", ref_id="", note: str = "") -> StockTransaction:
    qty = Decimal(qty)
    if qty <= 0:
        raise HTTPException(422, "Quantity must be positive")
    if mtype in IN_TYPES:
        inbound = True
    elif mtype in OUT_TYPES:
        inbound = False
    else:  # ADJUSTMENT
        if increase is None:
            raise HTTPException(422, "Adjustment direction required")
        inbound = increase
    if mtype in COST_REQUIRED and unit_cost is None:
        raise HTTPException(422, "unit_cost is required for this movement")

    bal = db.scalar(select(StockBalance).where(StockBalance.warehouse_id == warehouse_id,
                                               StockBalance.item_id == item_id,
                                               StockBalance.organization_id == org_id).with_for_update())
    if bal is None:
        bal = StockBalance(organization_id=org_id, warehouse_id=warehouse_id, item_id=item_id,
                           quantity=Decimal("0"), avg_cost=Decimal("0"))
        db.add(bal)
        db.flush()
    if inbound:
        cost = Decimal(unit_cost) if unit_cost is not None else bal.avg_cost
        new_qty = bal.quantity + qty
        bal.avg_cost = q4((bal.quantity * bal.avg_cost + qty * cost) / new_qty)
        bal.quantity = new_qty
        signed = qty
    else:
        if bal.quantity < qty:
            raise HTTPException(409, f"Insufficient stock: available {bal.quantity}, requested {qty}")
        cost = bal.avg_cost
        bal.quantity = bal.quantity - qty
        signed = -qty
    tx = StockTransaction(organization_id=org_id, warehouse_id=warehouse_id, item_id=item_id, type=mtype,
                          quantity=signed, unit_cost=q4(cost), project_id=project_id, cost_code_id=cost_code_id,
                          reference_type=ref_type, reference_id=str(ref_id), note=note, created_by=user_id)
    db.add(tx)
    return tx
