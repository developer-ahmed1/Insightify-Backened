"""
JWT authentication, password hashing, and Google OAuth verification.

Replaces Firebase-only auth with standard JWT + Google API OAuth.
Per AGENTS.md: "There is no Firebase authentication architecture in this project."
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    TokenExpiredError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

import bcrypt

# ---------------------------------------------------------------------------
# Password Hashing (Direct bcrypt to avoid passlib 72-byte bug)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT Token Creation & Verification
# ---------------------------------------------------------------------------

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.jwt_refresh_token_expire_days)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Returns:
        dict with token claims (sub, exp, type, etc.)

    Raises:
        TokenExpiredError: If the token has expired.
        InvalidTokenError: If the token is malformed or invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        error_str = str(e).lower()
        if "expired" in error_str:
            raise TokenExpiredError()
        raise InvalidTokenError()


def create_token_pair(user_id: str, email: str) -> dict:
    """
    Create both access and refresh tokens for a user.

    Returns RFC §2 tokens envelope:
    {
        "accessToken": "...",
        "refreshToken": "...",
        "expiresIn": 3600
    }
    """
    token_data = {"sub": user_id, "email": email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expiresIn": settings.jwt_access_token_expire_minutes * 60,
    }


# ---------------------------------------------------------------------------
# Google OAuth Token Verification (via google-auth library, no Firebase)
# ---------------------------------------------------------------------------

async def verify_google_id_token(id_token: str) -> dict:
    """
    Verify a Google ID token using the Google Auth library.

    Returns:
        dict with Google user info: uid, email, name, picture, email_verified

    Raises:
        AuthenticationError: If the token is invalid or expired.
    """
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        # Verify the ID token against Google's certificates
        idinfo = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            settings.google_client_id,
        )

        # Check that the token was issued by Google
        if idinfo.get("iss") not in [
            "accounts.google.com",
            "https://accounts.google.com",
        ]:
            raise AuthenticationError("Invalid Google token issuer")

        return {
            "uid": idinfo["sub"],
            "email": idinfo.get("email"),
            "email_verified": idinfo.get("email_verified", False),
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }
    except ValueError as e:
        logger.warning(f"Invalid Google ID token: {e}")
        raise AuthenticationError("Invalid or expired Google token")
    except Exception as e:
        logger.error(f"Google OAuth verification error: {e}")
        raise AuthenticationError(f"Google authentication failed: {str(e)}")


# ---------------------------------------------------------------------------
# FastAPI Security Dependencies
# ---------------------------------------------------------------------------

class JWTBearer(HTTPBearer):
    """JWT Bearer token security scheme for FastAPI."""

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        credentials = await super().__call__(request)
        if credentials is None:
            return None
        return credentials


# Global instance used as Depends()
jwt_bearer = JWTBearer()


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(jwt_bearer),
) -> dict:
    """
    Dependency: Extract and verify JWT from the Authorization header.

    Returns the decoded token payload dict containing 'sub' (user_id), 'email', etc.
    """
    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise InvalidTokenError()

    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenError()

    return payload


async def get_optional_token_payload(
    request: Request,
) -> Optional[dict]:
    """
    Dependency: Optionally extract JWT. Returns None if no token provided.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Legacy Firebase stubs (kept for backward compatibility during migration)
# ---------------------------------------------------------------------------

def init_firebase() -> None:
    """Legacy stub — Firebase is no longer used for auth."""
    logger.info("Firebase init skipped — using JWT auth")
