"""Data purge API - let an owner clear manually entered data."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import log_action
from app.datapurge.schemas import PurgePreviewOut, PurgeRequest, PurgeResultOut
from app.datapurge.service import CONFIRMATION_PHRASE, PurgeService
from app.db import get_db
from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/data", tags=["data"])


def get_service(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> PurgeService:
    return PurgeService(db, user)


def _require_owner(user: User = Depends(get_current_user)):
    """Purging data is an owner-level action; no other role may trigger it."""
    if not (user.role and user.role.name == "OWNER"):
        raise HTTPException(403, "Only the organization owner can delete data")
    return user


@router.get("/inventory", response_model=PurgePreviewOut)
def preview_purge(scope: str = "operational", service: PurgeService = Depends(get_service),
                  user: User = Depends(_require_owner)):
    """Show what a purge would delete, without deleting anything."""
    try:
        return service.preview(scope)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/purge", response_model=PurgeResultOut)
def purge_data(body: PurgeRequest, request: Request, service: PurgeService = Depends(get_service),
               user: User = Depends(_require_owner)):
    """Delete the organization's manually entered data. Irreversible."""
    try:
        result = service.purge(scope=body.scope, confirmation=body.confirmation)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    log_action(db=service.db, action="data.purge", org_id=user.organization_id, user_id=user.id,
               entity="organization", entity_id=str(user.organization_id), request=request,
               detail={"scope": body.scope, "rows_deleted": result["total_rows_deleted"]})
    return result


@router.get("/confirmation-phrase")
def confirmation_phrase(user: User = Depends(_require_owner)):
    """The phrase the client must echo back to confirm a purge."""
    return {"confirmation_phrase": CONFIRMATION_PHRASE}
