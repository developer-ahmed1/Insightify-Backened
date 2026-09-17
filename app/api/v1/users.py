"""
User & Profile API endpoints — RFC §3 User Profile, §4 Settings, §5 Activity.

GET   /api/v1/users/me                 — §3.1 Get Current User Profile
PATCH /api/v1/users/me                 — §3.2 Update User Profile
POST  /api/v1/users/me/avatar          — §3.3 Upload Profile Avatar
GET   /api/v1/users/me/settings        — §4.2 Get User Settings
PATCH /api/v1/users/me/settings        — §4.3 Update User Settings
GET   /api/v1/users/me/activity-summary — §5.2 Protection Summary
"""
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.models.detection import Detection
from app.schemas.user import (
    UserProfileResponse,
    UserStatsResponse,
    UserUpdateRequest,
    AvatarUploadResponse,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
    NotificationSettingsSchema,
)
from app.schemas.home import HomeSummaryResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


# ---------------------------------------------------------------------------
# §3.1 Get Current User Profile
# ---------------------------------------------------------------------------
@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's full profile with stats."""
    # Calculate stats
    total_scans = await db.scalar(
        select(func.count()).where(Detection.user_id == user.id)
    ) or 0
    total_threats = await db.scalar(
        select(func.count())
        .where(Detection.user_id == user.id)
        .where(Detection.verdict.in_(["Likely Scam", "Suspicious"]))
    ) or 0

    # Calculate rank (users with higher XP)
    rank = await db.scalar(
        select(func.count()).where(User.xp > user.xp)
    )
    rank = (rank or 0) + 1

    # Safety score (percentage of safe scans)
    safety_score = 92  # Default
    if total_scans > 0:
        safe_count = total_scans - total_threats
        safety_score = int((safe_count / total_scans) * 100)

    return UserProfileResponse(
        id=str(user.id),
        name=user.name or user.display_name,
        username=user.username,
        title=user.title,
        bio=user.bio,
        email=user.email,
        avatar=user.avatar,
        level=user.level,
        xp=user.xp,
        nextLevelXp=user.next_level_xp,
        rank=rank,
        stats=UserStatsResponse(
            safetyScore=safety_score,
            threatsPrevented=total_threats,
            scansCount=total_scans,
            reportsCount=0,
            verificationsCount=0,
        ),
    )


# ---------------------------------------------------------------------------
# §3.2 Update User Profile
# ---------------------------------------------------------------------------
@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    request: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile fields."""
    if request.name is not None:
        user.name = request.name
        user.display_name = request.name
    if request.username is not None:
        user.username = request.username
    if request.bio is not None:
        user.bio = request.bio
    if request.avatar is not None:
        user.avatar = request.avatar

    await db.flush()

    # Return updated profile
    return await get_my_profile(user=user, db=db)


# ---------------------------------------------------------------------------
# §3.3 Upload Profile Avatar
# ---------------------------------------------------------------------------
@router.post("/me/avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new profile avatar image."""
    # TODO: Upload to R2 storage
    # For now, store a placeholder URL
    avatar_url = f"/avatars/{user.id}/{file.filename}"
    user.avatar = avatar_url
    await db.flush()

    return AvatarUploadResponse(avatarUrl=avatar_url)


# ---------------------------------------------------------------------------
# §4.2 Get User Settings
# ---------------------------------------------------------------------------
@router.get("/me/settings", response_model=UserSettingsResponse)
async def get_my_settings(
    user: User = Depends(get_current_user),
):
    """Get current user's settings."""
    settings_data = user.settings or {}
    notif = settings_data.get("notifications", {})

    return UserSettingsResponse(
        profilePublic=settings_data.get("profilePublic", True),
        showOnLeaderboard=settings_data.get("showOnLeaderboard", True),
        anonymousReports=settings_data.get("anonymousReports", False),
        notifications=NotificationSettingsSchema(
            enabled=notif.get("enabled", True),
            scamAlerts=notif.get("scamAlerts", True),
            achievements=notif.get("achievements", True),
            leaderboardUpdates=notif.get("leaderboardUpdates", True),
        ),
    )


# ---------------------------------------------------------------------------
# §4.3 Update User Settings
# ---------------------------------------------------------------------------
@router.patch("/me/settings", response_model=UserSettingsResponse)
async def update_my_settings(
    request: UserSettingsUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's settings."""
    settings_data = dict(user.settings or {})

    if request.profilePublic is not None:
        settings_data["profilePublic"] = request.profilePublic
    if request.showOnLeaderboard is not None:
        settings_data["showOnLeaderboard"] = request.showOnLeaderboard
    if request.anonymousReports is not None:
        settings_data["anonymousReports"] = request.anonymousReports
    if request.notifications is not None:
        notif = settings_data.get("notifications", {})
        updates = request.notifications.model_dump(exclude_none=True)
        notif.update(updates)
        settings_data["notifications"] = notif

    user.settings = settings_data
    await db.flush()

    return await get_my_settings(user=user)


# ---------------------------------------------------------------------------
# §5.2 Activity Summary (Home Dashboard)
# ---------------------------------------------------------------------------
@router.get("/me/activity-summary", response_model=HomeSummaryResponse)
async def get_activity_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's protection/activity summary for home dashboard."""
    total_scans = await db.scalar(
        select(func.count()).where(Detection.user_id == user.id)
    ) or 0
    total_threats = await db.scalar(
        select(func.count())
        .where(Detection.user_id == user.id)
        .where(Detection.verdict.in_(["Likely Scam", "Suspicious"]))
    ) or 0

    safe_rate = 100
    if total_scans > 0:
        safe_rate = int(((total_scans - total_threats) / total_scans) * 100)

    return HomeSummaryResponse(
        isProtected=True,
        activeSince=user.created_at.isoformat() if user.created_at else None,
        timeframe="this_week",
        scansCount=total_scans,
        threatsBlocked=total_threats,
        safeInteractionsRate=safe_rate,
        alertsCount=0,
    )
