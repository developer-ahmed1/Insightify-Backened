"""
Authentication API endpoints — RFC §2 Auth & Onboarding APIs.

POST /api/v1/auth/register        — §2.1
POST /api/v1/auth/login           — §2.2
POST /api/v1/auth/google          — §2.3
POST /api/v1/auth/forgot-password — §2.4
POST /api/v1/auth/reset-password  — §2.5
POST /api/v1/auth/logout          — §2.6
POST /api/v1/auth/refresh         — §2.7
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
    verify_google_id_token,
    create_access_token,
)
from app.core.exceptions import (
    AlreadyExistsError,
    AuthenticationError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.models.user import User, UserStreak
from app.schemas.auth import (
    AuthResponse,
    AuthUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleAuthRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokensResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _user_to_auth_response(user: User, tokens: dict) -> AuthResponse:
    """Build AuthResponse from user and token pair."""
    return AuthResponse(
        user=AuthUserResponse(
            id=str(user.id),
            name=user.name or user.display_name,
            email=user.email,
            username=user.username,
            avatar=user.avatar,
            createdAt=user.created_at.isoformat() if user.created_at else None,
        ),
        tokens=TokensResponse(**tokens),
    )


# ---------------------------------------------------------------------------
# §2.1 Register
# ---------------------------------------------------------------------------
@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user with email and password."""
    # Check if email already exists
    existing = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing.scalar_one_or_none():
        raise AlreadyExistsError("User", "email", request.email)

    # Create user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        name=request.fullName,
        display_name=request.fullName,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create streak record
    streak = UserStreak(user_id=user.id)
    db.add(streak)
    await db.flush()

    # Generate tokens
    tokens = create_token_pair(str(user.id), user.email)

    logger.info(f"New user registered: {user.email}")
    return _user_to_auth_response(user, tokens)


# ---------------------------------------------------------------------------
# §2.2 Login
# ---------------------------------------------------------------------------
@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login with email and password."""
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise AuthenticationError("Invalid email or password")

    if not verify_password(request.password, user.password_hash):
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        raise AuthenticationError("Account has been deactivated")

    # Generate tokens
    tokens = create_token_pair(str(user.id), user.email)

    logger.info(f"User logged in: {user.email}")
    return _user_to_auth_response(user, tokens)


# ---------------------------------------------------------------------------
# §2.3 Google OAuth
# ---------------------------------------------------------------------------
@router.post("/google", response_model=AuthResponse)
async def google_auth(
    request: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with Google ID token.

    Verifies the token via Google API, creates or retrieves the user,
    and returns our own JWT tokens.
    """
    # Verify Google token
    google_user = await verify_google_id_token(request.idToken)

    # Check if user exists by google_uid
    result = await db.execute(
        select(User).where(User.google_uid == google_user["uid"])
    )
    user = result.scalar_one_or_none()

    if not user:
        # Check if email exists (link accounts)
        result = await db.execute(
            select(User).where(User.email == google_user["email"])
        )
        user = result.scalar_one_or_none()

        if user:
            # Link Google account to existing user
            user.google_uid = google_user["uid"]
            if not user.avatar and google_user.get("picture"):
                user.avatar = google_user["picture"]
        else:
            # Create new user
            user = User(
                email=google_user["email"],
                google_uid=google_user["uid"],
                name=google_user.get("name"),
                display_name=google_user.get("name"),
                avatar=google_user.get("picture"),
                is_active=True,
            )
            db.add(user)
            await db.flush()

            # Create streak
            streak = UserStreak(user_id=user.id)
            db.add(streak)
            await db.flush()

    if not user.is_active:
        raise AuthenticationError("Account has been deactivated")

    # Generate our JWT tokens
    tokens = create_token_pair(str(user.id), user.email)

    logger.info(f"Google auth for: {user.email}")
    return _user_to_auth_response(user, tokens)


# ---------------------------------------------------------------------------
# §2.4 Forgot Password
# ---------------------------------------------------------------------------
@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset. Generates a reset token."""
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    # Always return success to prevent email enumeration
    if user and user.password_hash:
        reset_token = secrets.token_urlsafe(32)
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.flush()

        # TODO: Send email with reset_token
        logger.info(f"Password reset requested for: {user.email}")

    return ForgotPasswordResponse()


# ---------------------------------------------------------------------------
# §2.5 Reset Password
# ---------------------------------------------------------------------------
@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a valid reset token."""
    result = await db.execute(
        select(User).where(User.password_reset_token == request.resetToken)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("Invalid or expired reset token")

    if user.password_reset_expires and user.password_reset_expires < datetime.now(timezone.utc):
        raise AuthenticationError("Reset token has expired")

    # Update password
    user.password_hash = hash_password(request.newPassword)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.flush()

    logger.info(f"Password reset completed for: {user.email}")
    return ResetPasswordResponse()


# ---------------------------------------------------------------------------
# §2.6 Logout
# ---------------------------------------------------------------------------
@router.post("/logout")
async def logout(request: LogoutRequest):
    """
    Logout — invalidate refresh token.

    NOTE: With stateless JWTs, true server-side invalidation requires
    a token blacklist (Redis-backed). For now, the client simply discards
    the tokens. A production implementation should add blacklisting.
    """
    # TODO: Add refresh token to Redis blacklist
    return {"success": True, "message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# §2.7 Refresh Token
# ---------------------------------------------------------------------------
@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh an expired access token using a valid refresh token."""
    payload = decode_token(request.refreshToken)

    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid refresh token")

    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id:
        raise AuthenticationError("Invalid refresh token")

    # Verify user still exists and is active
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise AuthenticationError("User not found or deactivated")

    # Issue new access token
    from app.core.security import create_access_token as _create
    from app.config import settings

    new_access = _create({"sub": str(user.id), "email": user.email})
    return RefreshTokenResponse(
        accessToken=new_access,
        expiresIn=settings.jwt_access_token_expire_minutes * 60,
    )
