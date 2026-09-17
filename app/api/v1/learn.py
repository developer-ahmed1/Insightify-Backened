"""
Learn / Daily Tip API — RFC §5.4.

GET /api/v1/learn/daily-tip — §5.4 Get Daily Safety Tip
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.daily_tip import DailySafetyTip
from app.schemas.home import DailyTipResponse

router = APIRouter(prefix="/learn", tags=["Learn"])


@router.get("/daily-tip", response_model=DailyTipResponse)
async def get_daily_tip(db: AsyncSession = Depends(get_db)):
    """Get today's daily safety tip."""
    today = date.today()

    # Try date-specific tip first
    result = await db.execute(
        select(DailySafetyTip)
        .where(DailySafetyTip.active_date == today)
        .where(DailySafetyTip.is_active == True)
    )
    tip = result.scalar_one_or_none()

    if not tip:
        # Fallback: get any active tip
        result = await db.execute(
            select(DailySafetyTip)
            .where(DailySafetyTip.is_active == True)
            .order_by(DailySafetyTip.created_at.desc())
            .limit(1)
        )
        tip = result.scalar_one_or_none()

    if not tip:
        return DailyTipResponse(
            id="default",
            title="Daily Safety Tip",
            content="Never share OTPs, passwords, or personal information with anyone. Stay safe!",
            category="credential_safety",
        )

    return DailyTipResponse(
        id=str(tip.id),
        title=tip.title,
        content=tip.content,
        category=tip.category,
    )
