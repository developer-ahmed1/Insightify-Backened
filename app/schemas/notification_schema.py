"""
Notification schemas — RFC §15.
"""
from typing import List, Optional
from app.schemas.common import BaseSchema


class NotificationItemResponse(BaseSchema):
    """Single notification."""
    id: str
    type: str  # scam_alert | achievement | leaderboard | report_update | system
    title: str
    message: Optional[str] = None
    isRead: bool = False
    data: Optional[dict] = None
    createdAt: str


class NotificationListResponse(BaseSchema):
    """Paginated notification list."""
    notifications: List[NotificationItemResponse] = []
    unreadCount: int = 0
    total: int = 0


class MarkReadRequest(BaseSchema):
    """Mark notifications as read."""
    notificationIds: List[str] = []  # Empty = mark all


# Admin: Create notification
class AdminNotificationCreateRequest(BaseSchema):
    """Admin: Send notification to a user or all users."""
    userId: Optional[str] = None  # None = broadcast to all
    type: str = "system"
    title: str
    message: Optional[str] = None
    data: Optional[dict] = None
