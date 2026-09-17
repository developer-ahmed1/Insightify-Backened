"""
Home dashboard schemas — RFC §5 Home Dashboard.
"""
from typing import List, Optional
from app.schemas.common import BaseSchema


# ---------------------------------------------------------------------------
# §5.2 Protection Summary
# ---------------------------------------------------------------------------
class HomeSummaryResponse(BaseSchema):
    """
    GET /api/v1/users/me/activity-summary — RFC §5.2

    Protection telemetry for the home dashboard shield card.
    """
    isProtected: bool = True
    activeSince: Optional[str] = None
    timeframe: str = "this_week"
    scansCount: int = 0
    threatsBlocked: int = 0
    safeInteractionsRate: int = 100
    alertsCount: int = 0


# ---------------------------------------------------------------------------
# §5.4 Daily Safety Tip
# ---------------------------------------------------------------------------
class DailyTipResponse(BaseSchema):
    """
    GET /api/v1/learn/daily-tip — RFC §5.4

    Single tip for home dashboard.
    """
    id: str
    title: str
    content: str
    category: str


# ---------------------------------------------------------------------------
# §5.3 Threat Feed Preview
# ---------------------------------------------------------------------------
class ThreatPreviewItem(BaseSchema):
    """Minimal threat item for home preview."""
    id: str
    riskLevel: str
    title: str
    description: str
    location: Optional[str] = None
    timeAgo: str = ""
    type: str = ""
    iconType: str = ""
    verifiedCount: int = 0


# ---------------------------------------------------------------------------
# §5.5 Notification Badge
# ---------------------------------------------------------------------------
class UnreadCountResponse(BaseSchema):
    """GET /api/v1/notifications/unread-count — RFC §5.5"""
    unreadCount: int = 0
