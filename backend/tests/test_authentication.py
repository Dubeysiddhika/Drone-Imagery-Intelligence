import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, get_db
from app.models.models import PasswordResetToken, User
from app.routes import auth
from app.services.security import JWT_SECRET_KEY, get_current_user, hash_password, verify_password


class AuthenticationRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.app = FastAPI()
        self.app.include_router(auth.router, prefix="/api/auth")

        @self.app.get("/protected")
        def protected(user: User = Depends(get_current_user)):
            return {"id": user.id, "email": user.normalized_email}

        self.app.dependency_overrides[get_db] = self._get_db
        self.client = TestClient(self.app)
        auth._login_failures.clear()

    def tearDown(self):
        auth._login_failures.clear()
        self.client.close()
        self.engine.dispose()

    def _get_db(self):
        with self.sessions() as session:
            yield session

    def register(self, email="siddhika@gmail.com", password="SecurePassword9!", full_name="  Siddhika Rao  "):
        return self.client.post("/api/auth/register", json={"full_name": full_name, "email": email, "password": password})

    def test_register_normalizes_email_and_name_and_stores_argon2_only(self):
        response = self.register("  SIDDHIKA@GMAIL.COM  ")
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"], {"id": 1, "full_name": "Siddhika Rao", "email": "siddhika@gmail.com"})
        with self.sessions() as session:
            user = session.query(User).one()
            self.assertTrue(user.password_hash.startswith("$argon2id$"))
            self.assertNotIn("SecurePassword9!", user.password_hash)
            self.assertTrue(verify_password("SecurePassword9!", user.password_hash))
        duplicate = self.register("siddhika@gmail.com")
        self.assertEqual(duplicate.status_code, 409)

    def test_email_validation_rejects_malformed_addresses(self):
        for email in ("", "siddhikagmail.com", "@gmail.com", "siddhika@", "siddhika@gmail", "x@-domain.com", "a..b@example.com"):
            with self.subTest(email=email):
                response = self.register(email=email)
                self.assertEqual(response.status_code, 422, response.text)

    def test_password_policy_rejects_each_missing_requirement(self):
        invalid_passwords = (
            "Short9!a", "lowercasepass9!", "UPPERCASEPASS9!", "NoDigitsHere!!", "NoSpecialChar9", "Has Space9!Ab",
        )
        for index, password in enumerate(invalid_passwords):
            with self.subTest(password_index=index):
                response = self.register(email=f"person{index}@example.com", password=password)
                self.assertEqual(response.status_code, 422, response.text)

    def test_legacy_complexity_password_can_sign_in_and_cookie_is_http_only(self):
        # Model a pre-existing account created before the current registration
        # password policy. Login must remain compatible with its existing hash.
        with self.sessions() as session:
            session.add(User(
                full_name="Siddhika Rao",
                normalized_email="siddhika@gmail.com",
                password_hash=hash_password("Legacy Password"),
            ))
            session.commit()

        response = self.client.post("/api/auth/login", json={"email": " SIDDHIKA@GMAIL.COM ", "password": "Legacy Password"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("token", response.json())
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertNotIn("password_hash", json.dumps(response.json()))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.assertEqual(self.client.get("/protected").json()["email"], "siddhika@gmail.com")
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.client.get("/protected").status_code, 401)

    def test_missing_and_expired_sessions_are_rejected_and_invalid_login_is_generic(self):
        self.assertEqual(self.client.get("/protected").status_code, 401)
        self.register()
        wrong = self.client.post("/api/auth/login", json={"email": "siddhika@gmail.com", "password": "wrong password"})
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.json()["detail"], "Invalid email or password.")
        expired = jwt.encode({
            "sub": "1", "ver": 0,
            "iat": datetime.utcnow() - timedelta(hours=2),
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iss": "aerovision-intelligence", "aud": "aerovision-client",
        }, JWT_SECRET_KEY, algorithm="HS256")
        self.client.cookies.set("aerovision_session", expired)
        self.assertEqual(self.client.get("/protected").status_code, 401)

    def test_login_rate_limiter_blocks_repeated_failures(self):
        self.register()
        for _ in range(auth.LOGIN_MAX_FAILURES):
            self.client.post("/api/auth/login", json={"email": "siddhika@gmail.com", "password": "incorrect"})
        limited = self.client.post("/api/auth/login", json={"email": "siddhika@gmail.com", "password": "incorrect"})
        self.assertEqual(limited.status_code, 429)

    def test_password_reset_request_is_non_enumerating_when_smtp_is_missing(self):
        self.register()
        with patch.dict(os.environ, {"SMTP_HOST": "", "SMTP_FROM": "", "SMTP_PORT": "587"}):
            known = self.client.post("/api/auth/password-reset/request", json={"email": "siddhika@gmail.com"})
            unknown = self.client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"})
        self.assertEqual(known.status_code, 202)
        self.assertEqual(known.json(), unknown.json())
        self.assertFalse(known.json()["email_delivery_configured"])
        with self.sessions() as session:
            self.assertEqual(session.query(PasswordResetToken).count(), 0)

    def test_reset_token_is_hashed_single_use_and_revokes_existing_sessions(self):
        self.register()
        self.client.post("/api/auth/login", json={"email": "siddhika@gmail.com", "password": "SecurePassword9!"})
        raw_token = "safe-reset-token-value-0123456789abcdef"
        with self.sessions() as session:
            user = session.query(User).one()
            session.add(PasswordResetToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.utcnow() + timedelta(minutes=5),
            ))
            session.commit()
        response = self.client.post("/api/auth/password-reset/confirm", json={"token": raw_token, "new_password": "NewSecurePassword8#"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.client.cookies.clear()
        old_login = self.client.post("/api/auth/login", json={"email": "siddhika@gmail.com", "password": "SecurePassword9!"})
        self.assertEqual(old_login.status_code, 401)
        new_login = self.client.post("/api/auth/login", json={"email": "siddhika@gmail.com", "password": "NewSecurePassword8#"})
        self.assertEqual(new_login.status_code, 200)
        used_again = self.client.post("/api/auth/password-reset/confirm", json={"token": raw_token, "new_password": "AnotherSecurePass7!"})
        self.assertEqual(used_again.status_code, 400)
        with self.sessions() as session:
            reset = session.query(PasswordResetToken).one()
            self.assertEqual(reset.token_hash, hashlib.sha256(raw_token.encode()).hexdigest())
            self.assertIsNotNone(reset.used_at)


if __name__ == "__main__":
    unittest.main()
