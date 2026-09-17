"""
Notifications API — RFC §15.

GET /api/v1/notifications/unread-count — §15.2 Get Unread Count
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.schemas.home import UnreadCountResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread notifications."""
    count = await db.scalar(
        select(func.count())
        .where(Notification.user_id == user.id)
        .where(Notification.is_read == False)
    ) or 0

    return UnreadCountResponse(unreadCount=count)
