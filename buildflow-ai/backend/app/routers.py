import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import rbac
from app.audit import log_action
from app.db import get_db
from app.boq.models import DEFAULT_UNITS, Unit
from app.deps import get_current_user, org_scoped, require_permission
from app.models import AuditLog, Organization, Permission, Role, User
from app.schemas import AuditOut, Login, Refresh, RegisterOrg, TokenPair, UserCreate, UserOut
from app.security import (create_access_token, create_refresh_token, decode_token, hash_password,
                          verify_password)

auth = APIRouter(prefix="/auth", tags=["auth"])
users = APIRouter(prefix="/users", tags=["users"])
audit = APIRouter(prefix="/audit-logs", tags=["audit"])


def _user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, full_name=u.full_name, is_active=u.is_active, role_name=u.role.name)


def _tokens(u: User) -> TokenPair:
    return TokenPair(access_token=create_access_token(u.id, u.organization_id, u.token_version),
                     refresh_token=create_refresh_token(u.id, u.organization_id, u.token_version))


def _ensure_permissions(db: Session) -> dict[str, Permission]:
    existing = {p.code: p for p in db.scalars(select(Permission))}
    for code, desc in rbac.PERMISSIONS.items():
        if code not in existing:
            existing[code] = Permission(code=code, description=desc)
            db.add(existing[code])
    db.flush()
    return existing


@auth.post("/register-organization", response_model=TokenPair, status_code=201)
def register_organization(body: RegisterOrg, request: Request, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    org = Organization(name=body.organization_name)
    db.add(org)
    db.flush()
    perms = _ensure_permissions(db)
    roles: dict[str, Role] = {}
    for name, (codes, limit) in rbac.DEFAULT_ROLES.items():
        roles[name] = Role(organization_id=org.id, name=name, approval_limit=limit,
                           permissions=[perms[c] for c in codes])
        db.add(roles[name])
    db.flush()
    for code, name in DEFAULT_UNITS:
        db.add(Unit(organization_id=org.id, code=code, name=name))
    owner = User(organization_id=org.id, email=body.email.lower(), full_name=body.owner_name,
                 password_hash=hash_password(body.password), role_id=roles["OWNER"].id)
    db.add(owner)
    db.commit()
    log_action(db, action="org.register", org_id=org.id, user_id=owner.id, entity="organization",
               entity_id=org.id, request=request)
    return _tokens(owner)


@auth.post("/login", response_model=TokenPair)
def login(body: Login, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or user.deleted_at or not verify_password(body.password, user.password_hash):
        log_action(db, action="auth.login", org_id=user.organization_id if user else None,
                   user_id=user.id if user else None, result="failure", request=request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    log_action(db, action="auth.login", org_id=user.organization_id, user_id=user.id, request=request)
    return _tokens(user)


@auth.post("/refresh", response_model=TokenPair)
def refresh(body: Refresh, db: Session = Depends(get_db)):
    bad = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise bad
    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active or user.token_version != payload["ver"]:
        raise bad
    return _tokens(user)


@auth.post("/logout-all", status_code=204)
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1  # revokes all refresh tokens
    db.commit()


@users.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@users.get("", response_model=list[UserOut])
def list_users(user: User = Depends(require_permission("users.read")), db: Session = Depends(get_db)):
    rows = db.scalars(org_scoped(User, user).where(User.deleted_at.is_(None))).all()
    return [_user_out(u) for u in rows]


@users.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request,
                actor: User = Depends(require_permission("users.manage")), db: Session = Depends(get_db)):
    role = db.scalar(select(Role).where(Role.organization_id == actor.organization_id, Role.name == body.role_name))
    if not role:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown role")
    if role.name == "OWNER" and actor.role.name != "OWNER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an owner can create owners")
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    u = User(organization_id=actor.organization_id, email=body.email.lower(), full_name=body.full_name,
             password_hash=hash_password(body.password), role_id=role.id)
    db.add(u)
    db.commit()
    log_action(db, action="user.create", org_id=actor.organization_id, user_id=actor.id, entity="user",
               entity_id=u.id, request=request, detail={"role": role.name})
    return _user_out(u)


@audit.get("", response_model=list[AuditOut])
def list_audit(limit: int = 100, user: User = Depends(require_permission("audit.read")),
               db: Session = Depends(get_db)):
    q = (select(AuditLog).where(AuditLog.organization_id == user.organization_id)
         .order_by(AuditLog.created_at.desc()).limit(min(limit, 500)))
    return db.scalars(q).all()
