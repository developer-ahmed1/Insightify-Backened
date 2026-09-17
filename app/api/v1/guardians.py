"""
Guardians API — RFC §14 Public Guardian Profile.

GET /api/v1/guardians/{userId} — §14.1 Get Public Guardian Profile
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.detection import Detection
from app.models.gamification import UserBadge
from app.schemas.user import UserProfileResponse, UserStatsResponse

router = APIRouter(prefix="/guardians", tags=["Guardians"])


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_guardian_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a public guardian profile by user ID."""
    try:
        uid = UUID(user_id)
    except (ValueError, TypeError):
        raise NotFoundError("Guardian", user_id)

    result = await db.execute(
        select(User).where(User.id == uid).where(User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("Guardian", user_id)

    # Check if profile is public
    settings = user.settings or {}
    if not settings.get("profilePublic", True):
        raise NotFoundError("Guardian", user_id)

    # Stats
    total_scans = await db.scalar(
        select(func.count()).where(Detection.user_id == user.id)
    ) or 0
    total_threats = await db.scalar(
        select(func.count())
        .where(Detection.user_id == user.id)
        .where(Detection.verdict.in_(["Likely Scam", "Suspicious"]))
    ) or 0
    total_badges = await db.scalar(
        select(func.count()).where(UserBadge.user_id == user.id)
    ) or 0

    rank = await db.scalar(
        select(func.count()).where(User.xp > user.xp)
    )
    rank = (rank or 0) + 1

    return UserProfileResponse(
        id=str(user.id),
        name=user.name or user.display_name,
        username=user.username,
        title=user.title,
        bio=user.bio,
        email="",  # Hide email for public profiles
        avatar=user.avatar,
        level=user.level,
        xp=user.xp,
        nextLevelXp=user.next_level_xp,
        rank=rank,
        stats=UserStatsResponse(
            safetyScore=92,
            threatsPrevented=total_threats,
            scansCount=total_scans,
        ),
    )
