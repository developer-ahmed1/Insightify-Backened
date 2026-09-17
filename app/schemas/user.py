"""
User & Profile schemas — RFC §3 User & Profile APIs, §4 Settings APIs.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


# ---------------------------------------------------------------------------
# §3.1 Get Current User Profile
# ---------------------------------------------------------------------------
class UserStatsResponse(BaseSchema):
    """User activity statistics nested in profile."""
    safetyScore: int = 0
    threatsPrevented: int = 0
    scansCount: int = 0
    reportsCount: int = 0
    verificationsCount: int = 0


class UserProfileResponse(BaseSchema):
    """
    GET /api/v1/users/me — RFC §3.1

    Full profile response with XP, level, rank, safety score, and activity counts.
    """
    id: str
    name: Optional[str] = None
    username: Optional[str] = None
    title: Optional[str] = None
    bio: Optional[str] = None
    email: str
    avatar: Optional[str] = None
    level: int = 1
    xp: int = 0
    nextLevelXp: int = 200
    rank: Optional[int] = None
    stats: UserStatsResponse = UserStatsResponse()


# ---------------------------------------------------------------------------
# §3.2 Update User Profile
# ---------------------------------------------------------------------------
class UserUpdateRequest(BaseSchema):
    """PATCH /api/v1/users/me — RFC §3.2"""
    name: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)
    avatar: Optional[str] = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# §3.3 Upload Profile Avatar
# ---------------------------------------------------------------------------
class AvatarUploadResponse(BaseSchema):
    """POST /api/v1/users/me/avatar — RFC §3.3"""
    avatarUrl: str


# ---------------------------------------------------------------------------
# §4.2 / §4.3 User Settings
# ---------------------------------------------------------------------------
class NotificationSettingsSchema(BaseSchema):
    """Notification sub-settings."""
    enabled: Optional[bool] = None
    scamAlerts: Optional[bool] = None
    achievements: Optional[bool] = None
    leaderboardUpdates: Optional[bool] = None


class UserSettingsResponse(BaseSchema):
    """GET /api/v1/users/me/settings — RFC §4.2"""
    profilePublic: bool = True
    showOnLeaderboard: bool = True
    anonymousReports: bool = False
    notifications: NotificationSettingsSchema = NotificationSettingsSchema(
        enabled=True, scamAlerts=True, achievements=True, leaderboardUpdates=True
    )


class UserSettingsUpdateRequest(BaseSchema):
    """PATCH /api/v1/users/me/settings — RFC §4.3"""
    profilePublic: Optional[bool] = None
    showOnLeaderboard: Optional[bool] = None
    anonymousReports: Optional[bool] = None
    notifications: Optional[NotificationSettingsSchema] = None


# ---------------------------------------------------------------------------
# Legacy schemas (kept for backward compatibility)
# ---------------------------------------------------------------------------
class UserCreate(BaseSchema):
    """Internal schema for creating a user."""
    email: str
    password_hash: Optional[str] = None
    name: Optional[str] = None
    google_uid: Optional[str] = None
    avatar: Optional[str] = None


class UserResponse(BaseSchema):
    """Basic user response (used in various places)."""
    id: UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    xp: int = 0
    level: int = 1
    is_premium: bool = False
    subscription_tier: str = "free"
    created_at: datetime


class UserProfile(BaseSchema):
    """Legacy full user profile."""
    id: UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    xp: int = 0
    level: int = 1
    is_premium: bool = False
    subscription_tier: str = "free"
    total_detections: int = 0
    total_posts: int = 0
    total_badges: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    email_notifications: bool = True
    push_notifications: bool = True
    created_at: datetime


class UserUpdate(BaseSchema):
    """Legacy schema for updating user profile."""
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None


class StreakResponse(BaseSchema):
    """User streak information."""
    current_streak: int
    longest_streak: int
    last_activity_date: Optional[date] = None
    next_milestone: int
    days_to_milestone: int


class RateLimitInfo(BaseSchema):
    """Rate limit info for single action."""
    action: str
    limit: int
    used: int
    remaining: int
    allowed: bool


class UserLimitsResponse(BaseSchema):
    """User's current rate limits."""
    tier: str
    limits: dict[str, RateLimitInfo]
    reset_at: str = "midnight UTC"
