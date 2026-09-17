"""
Achievements API — RFC §13.

GET /api/v1/achievements — §13.1 Get User Achievements
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.gamification import Badge, UserBadge
from app.schemas.gamification import AchievementResponse, AchievementsListResponse

router = APIRouter(prefix="/achievements", tags=["Achievements"])


@router.get("", response_model=AchievementsListResponse)
async def get_achievements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all achievements with unlock status for current user."""
    # Get all active badges
    result = await db.execute(
        select(Badge).where(Badge.is_active == True).order_by(Badge.category)
    )
    badges = result.scalars().all()

    # Get user's earned badges
    earned_result = await db.execute(
        select(UserBadge).where(UserBadge.user_id == user.id)
    )
    earned_map = {str(ub.badge_id): ub for ub in earned_result.scalars().all()}

    achievements = []
    unlocked_count = 0
    locked_count = 0

    for badge in badges:
        user_badge = earned_map.get(str(badge.id))
        is_unlocked = user_badge is not None

        if is_unlocked:
            unlocked_count += 1
        else:
            locked_count += 1

        # Extract progress from criteria if available
        target = 1
        current = 1 if is_unlocked else 0
        if badge.criteria:
            target = badge.criteria.get("threshold", 1)

        achievements.append(AchievementResponse(
            id=str(badge.id),
            title=badge.name,
            description=badge.description,
            iconName=None,
            iconUrl=badge.icon_url,
            category=badge.category,
            xpReward=badge.xp_reward,
            unlocked=is_unlocked,
            unlockedDate=user_badge.earned_at.isoformat() if user_badge else None,
            currentProgress=target if is_unlocked else current,
            targetProgress=target,
        ))

    return AchievementsListResponse(
        achievements=achievements,
        totalUnlocked=unlocked_count,
        totalLocked=locked_count,
    )
