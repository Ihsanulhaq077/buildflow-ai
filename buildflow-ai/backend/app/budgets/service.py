"""Budget commitment / actual posting. Deterministic; row-locked to avoid lost updates."""
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.boq.models import ApprovalStatus
from app.budgets.models import Budget, BudgetLine


def _line(db: Session, org_id, project_id, cost_code_id) -> BudgetLine:
    q = (select(BudgetLine).join(Budget, Budget.id == BudgetLine.budget_id)
         .where(Budget.organization_id == org_id, Budget.project_id == project_id,
                Budget.status == ApprovalStatus.APPROVED, BudgetLine.cost_code_id == cost_code_id)
         .with_for_update())
    line = db.scalar(q)
    if line is None:
        raise HTTPException(409, "No approved budget line for this project and cost code")
    return line


def commit(db: Session, org_id, project_id, amounts_by_cost_code: dict[uuid.UUID, Decimal]) -> None:
    """Add PO value to committed cost. Blocks if it would exceed the line's revised budget."""
    for cc, amt in amounts_by_cost_code.items():
        line = _line(db, org_id, project_id, cc)
        if line.committed_amount + amt > line.revised_amount:
            raise HTTPException(409, f"Commitment would exceed budget line '{line.description}': "
                                     f"available {line.revised_amount - line.committed_amount}, needed {amt}. "
                                     "Revise the budget first.")
        line.committed_amount += amt


def release(db: Session, org_id, project_id, amounts_by_cost_code: dict[uuid.UUID, Decimal]) -> None:
    for cc, amt in amounts_by_cost_code.items():
        line = _line(db, org_id, project_id, cc)
        line.committed_amount = max(Decimal("0"), line.committed_amount - amt)


def record_actual(db: Session, org_id, project_id, amounts_by_cost_code: dict[uuid.UUID, Decimal]) -> None:
    for cc, amt in amounts_by_cost_code.items():
        _line(db, org_id, project_id, cc).actual_amount += amt


def group(pairs) -> dict[uuid.UUID, Decimal]:
    out: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for cc, amt in pairs:
        out[cc] += amt
    return dict(out)


def record_direct_cost(db: Session, org_id, project_id, amounts_by_cost_code: dict[uuid.UUID, Decimal]) -> None:
    """Costs with no PO stage (labour): committed and actual move together. Never blocks work that already
    happened; an overrun shows up as a negative 'remaining' on the budget."""
    for cc, amt in amounts_by_cost_code.items():
        line = _line(db, org_id, project_id, cc)
        line.committed_amount += amt
        line.actual_amount += amt
