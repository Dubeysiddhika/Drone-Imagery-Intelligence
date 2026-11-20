"""Password hashing, signed session JWTs, and protected-route dependencies."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import User


SESSION_COOKIE_NAME = "aerovision_session"
SESSION_TTL_SECONDS = 30 * 60
_configured_secret = os.getenv("JWT_SECRET_KEY", "").strip()
_production = os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}
if _production and len(_configured_secret.encode("utf-8")) < 32:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters in production.")
JWT_SECRET_KEY = _configured_secret or secrets.token_urlsafe(48)

password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return password_hasher.verify(encoded_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, ValueError):
        return False


def create_session_jwt(user: User) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user.id),
        "ver": user.token_version,
        "iat": now,
        "exp": now + timedelta(seconds=SESSION_TTL_SECONDS),
        "iss": "aerovision-intelligence",
        "aud": "aerovision-client",
    }
    return jwt.encode(claims, JWT_SECRET_KEY, algorithm="HS256")


def set_session_cookie(response, user: User) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_jwt(user),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=_production,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=_production,
        samesite="lax",
        path="/",
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=["HS256"],
            issuer="aerovision-intelligence",
            audience="aerovision-client",
            options={"require": ["sub", "ver", "iat", "exp"]},
        )
        user_id = int(claims["sub"])
        token_version = int(claims["ver"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired.") from error
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None or user.token_version != token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired.")
    return user

