import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing credentials")
    if creds is None:
        raise unauthorized
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        raise unauthorized
    user = db.get(User, uuid.UUID(payload["sub"]))
    if (user is None or not user.is_active or user.deleted_at is not None
            or str(user.organization_id) != payload["org"]):
        raise unauthorized
    return user


def require_permission(code: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if code not in {p.code for p in user.role.permissions}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")
        return user
    return checker


def org_scoped(model, user: User):
    """Every tenant-owned query must start from this helper."""
    return select(model).where(model.organization_id == user.organization_id)


def get_owned(db, model, obj_id, user: User, code: int = 404):
    """Fetch a tenant-owned row or fail. Cross-tenant ids look identical to missing ones."""
    obj = db.get(model, obj_id)
    if obj is None or obj.organization_id != user.organization_id or getattr(obj, "deleted_at", None):
        raise HTTPException(code, f"{model.__name__} not found" if code == 404 else f"Invalid {model.__name__} reference")
    return obj


def has_permission(user: User, code: str) -> bool:
    return code in {p.code for p in user.role.permissions}
