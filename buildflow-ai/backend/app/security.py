import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def _token(user_id: uuid.UUID, org_id: uuid.UUID, kind: str, ttl: timedelta, version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "org": str(org_id), "type": kind, "ver": version, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_access_token(user_id, org_id, version: int) -> str:
    return _token(user_id, org_id, "access", timedelta(minutes=settings.access_token_minutes), version)


def create_refresh_token(user_id, org_id, version: int) -> str:
    return _token(user_id, org_id, "refresh", timedelta(days=settings.refresh_token_days), version)


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload
