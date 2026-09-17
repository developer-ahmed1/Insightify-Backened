"""
FastAPI dependency injection for authentication and database sessions.

Replaces Firebase-based auth with JWT-based auth per RFC §2.
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_token_payload, get_optional_token_payload
from app.core.exceptions import AuthenticationError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency: Extract the current authenticated user from a JWT token.

    The token payload contains 'sub' = user_id (UUID string).
    Looks up the user in the database and returns the User model.

    Raises:
        AuthenticationError: If user not found or deactivated.
    """
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Invalid token: missing user identifier")

    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        raise AuthenticationError("Invalid token: malformed user identifier")

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("Account has been deactivated")

    return user


async def get_optional_user(
    payload: Optional[dict] = Depends(get_optional_token_payload),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency: Optionally extract the current user.
    Returns None if no token is provided (public endpoints).
    """
    if payload is None:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        return None

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user


async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Dependency: Require the current user to have admin privileges.

    Raises:
        ForbiddenError: If user is not an admin.
    """
    if not user.is_admin:
        raise ForbiddenError("Admin access required")
    return user
