from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(db: Session, *, action: str, org_id=None, user_id=None, entity: str = "",
               entity_id: str = "", result: str = "success", request: Request | None = None,
               detail: dict | None = None) -> None:
    db.add(AuditLog(
        organization_id=org_id, user_id=user_id, action=action, entity=entity,
        entity_id=str(entity_id), result=result,
        ip=request.client.host if request and request.client else None,
        detail=detail or {},
    ))
    db.commit()
