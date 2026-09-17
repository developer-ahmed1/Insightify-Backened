"""
Leaderboard API — RFC §12.

GET /api/v1/leaderboard — §12.1 Get Leaderboard
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.gamification import LeaderboardResponse, LeaderboardEntryResponse

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@router.get("", response_model=LeaderboardResponse)
async def get_leaderboard(
    period: str = Query("daily", description="daily | weekly | monthly | all_time"),
    limit: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get leaderboard entries sorted by XP."""
    # TODO: Add period-based filtering (requires XP history tracking)
    # For now, using all-time XP as the ranking metric
    result = await db.execute(
        select(User)
        .where(User.is_active == True)
        .order_by(User.xp.desc())
        .limit(limit)
    )
    users = result.scalars().all()

    # Get current user's rank
    user_rank = await db.scalar(
        select(func.count()).where(User.xp > user.xp).where(User.is_active == True)
    )
    user_rank = (user_rank or 0) + 1

    entries = []
    for i, u in enumerate(users, 1):
        entries.append(LeaderboardEntryResponse(
            rank=i,
            userId=str(u.id),
            name=u.name or u.display_name,
            avatar=u.avatar,
            score=u.xp,
            level=u.level,
            isCurrentUser=(u.id == user.id),
        ))

    return LeaderboardResponse(
        period=period,
        entries=entries,
        currentUserRank=user_rank,
    )
