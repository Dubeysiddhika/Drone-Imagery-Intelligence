"""Account registration, login, cookie sessions, and email password recovery."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import update

from ..models.database import get_db
from ..models.models import PasswordResetToken, User
from ..services.security import (
    SESSION_TTL_SECONDS,
    clear_session_cookie,
    get_current_user,
    hash_password,
    password_hasher,
    set_session_cookie,
    verify_password,
)

router = APIRouter()
logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)
RESET_TTL = timedelta(minutes=30)
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 5
_login_failures: dict[str, deque[float]] = defaultdict(deque)
_login_lock = threading.Lock()


def _normalize_email(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Enter a valid email address.")
    normalized = value.strip().casefold()
    if len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Enter a valid email address with a complete domain.")
    local, domain = normalized.rsplit("@", 1)
    if len(local) > 64 or ".." in local or domain.endswith("."):
        raise ValueError("Enter a valid email address.")
    return normalized


class EmailInput(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_check_email(cls, value: object) -> str:
        return _normalize_email(value)


class RegisterRequest(EmailInput):
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Full name is required.")
        return value.strip()


class LoginRequest(EmailInput):
    password: str = Field(min_length=1, max_length=256)


class ResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def password_policy_errors(password: str) -> list[str]:
    requirements = [
        (len(password) >= 12, "Use at least 12 characters."),
        (any(character.isupper() for character in password), "Add an uppercase letter."),
        (any(character.islower() for character in password), "Add a lowercase letter."),
        (any(character.isdigit() for character in password), "Add a number."),
        (any(not character.isalnum() and not character.isspace() for character in password), "Add a special character."),
        (not any(character.isspace() for character in password), "Do not use whitespace."),
    ]
    return [message for satisfied, message in requirements if not satisfied]


def _validate_password(password: str) -> None:
    errors = password_policy_errors(password)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Password does not meet the security requirements.", "password_requirements": errors})


def _allow_login_attempt(client_ip: str) -> None:
    now = time.monotonic()
    with _login_lock:
        attempts = _login_failures[client_ip]
        while attempts and now - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= LOGIN_MAX_FAILURES:
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again later.")


def _record_failed_login(client_ip: str) -> None:
    now = time.monotonic()
    with _login_lock:
        attempts = _login_failures[client_ip]
        while attempts and now - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        attempts.append(now)


def _clear_login_failures(client_ip: str) -> None:
    with _login_lock:
        _login_failures.pop(client_ip, None)


def _user_response(user: User) -> dict:
    return {"id": user.id, "full_name": user.full_name, "email": user.normalized_email}


def _smtp_configuration() -> dict | None:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        return None
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        return None
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().casefold() in {"1", "true", "yes", "on"}
    if not 1 <= port <= 65535 or not EMAIL_PATTERN.fullmatch(sender.casefold()) or not use_tls:
        return None
    return {
        "host": host,
        "port": port,
        "sender": sender,
        "username": os.getenv("SMTP_USERNAME", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "use_tls": use_tls,
    }


def _send_reset_email(recipient: str, token: str, smtp: dict) -> None:
    base_url = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
    reset_url = f"{base_url}/reset-password?{urlencode({'token': token})}"
    message = EmailMessage()
    message["Subject"] = "AEROVISION INTELLIGENCE password reset"
    message["From"] = smtp["sender"]
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your AEROVISION INTELLIGENCE account. "
        f"This single-use link expires in 30 minutes:\n\n{reset_url}\n\n"
        "If you did not request this, you can ignore this message."
    )
    context = ssl.create_default_context()
    if smtp["port"] == 465:
        connection = smtplib.SMTP_SSL(smtp["host"], smtp["port"], timeout=10, context=context)
        with connection as client:
            if smtp["username"]:
                client.login(smtp["username"], smtp["password"])
            client.send_message(message)
    else:
        with smtplib.SMTP(smtp["host"], smtp["port"], timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            if smtp["username"]:
                client.login(smtp["username"], smtp["password"])
            client.send_message(message)


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Create a new account")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    _validate_password(payload.password)
    user = User(
        full_name=payload.full_name,
        normalized_email=str(payload.email).casefold(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from error
    db.refresh(user)
    return {"user": _user_response(user), "message": "Account created successfully."}


@router.post("/login", summary="Sign in and create a secure session")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _allow_login_attempt(client_ip)
    user = db.query(User).filter(User.normalized_email == str(payload.email).casefold()).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        _record_failed_login(client_ip)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _clear_login_failures(client_ip)
    # Upgrade legacy Argon2 settings only after a successful verification.
    # Avoid check_needs_rehash on an unrecognized/legacy hash format.
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.commit()
    set_session_cookie(response, user)
    return {"user": _user_response(user), "expires_in": SESSION_TTL_SECONDS}


@router.post("/logout", summary="End the current session")
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    clear_session_cookie(response)
    return {"message": "Signed out."}


@router.get("/me", summary="Get the signed-in account")
def get_me(user: User = Depends(get_current_user)):
    return {"user": _user_response(user)}


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED, summary="Request password reset instructions")
def request_password_reset(payload: EmailInput, db: Session = Depends(get_db)):
    smtp = _smtp_configuration()
    if smtp is not None:
        user = db.query(User).filter(User.normalized_email == str(payload.email).casefold(), User.is_active.is_(True)).first()
        if user is not None:
            raw_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            ).delete(synchronize_session=False)
            db.add(PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.utcnow() + RESET_TTL,
            ))
            db.commit()
            try:
                _send_reset_email(user.normalized_email, raw_token, smtp)
            except (OSError, smtplib.SMTPException, ssl.SSLError):
                logger.warning("Password reset email delivery failed.")
    return {
        "message": "If an account matches, the request has been processed. This response does not confirm account existence or email delivery.",
        "email_delivery_configured": smtp is not None,
    }


@router.post("/password-reset/confirm", summary="Set a new password using a reset link")
def confirm_password_reset(payload: ResetConfirmRequest, db: Session = Depends(get_db)):
    _validate_password(payload.new_password)
    now = datetime.utcnow()
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > now,
    ).first()
    if reset is None:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")
    claimed = db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.id == reset.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")
    user = db.query(User).filter(User.id == reset.user_id, User.is_active.is_(True)).first()
    if user is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != reset.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
    db.commit()
    return {"message": "Password updated. Sign in using your new password."}

