"""
Threat Feed API endpoints — RFC §6 Community Threat Feed, §7 Threat Feed Detail.

GET  /api/v1/feed                    — §6.1 Get Threat Feed List
GET  /api/v1/feed/preview            — §5.3 Threat Feed Preview (Home)
GET  /api/v1/feed/{threatId}         — §7.2 Get Threat Detail Dossier
POST /api/v1/feed/{threatId}/bookmark — §6.2 Toggle Feed Bookmark
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.models.threat_post import ThreatPost, FeedBookmark
from app.schemas.feed import (
    ThreatFeedItemResponse,
    ThreatFeedListResponse,
    ThreatDetailResponse,
    FeedBookmarkResponse,
    FeedPaginationResponse,
    ThreatMediaItem,
    ThreatReportedBy,
    ThreatExampleContent,
)
from app.schemas.home import ThreatPreviewItem

logger = get_logger(__name__)

router = APIRouter(prefix="/feed", tags=["Threat Feed"])


def _threat_to_item(tp: ThreatPost, is_bookmarked: bool = False) -> ThreatFeedItemResponse:
    """Convert ThreatPost model to RFC feed item response."""
    media_items = []
    if tp.media:
        for m in tp.media:
            media_items.append(ThreatMediaItem(
                id=m.get("id", ""),
                type=m.get("type", "image"),
                url=m.get("url", ""),
                thumbnailUrl=m.get("thumbnailUrl"),
                title=m.get("title"),
            ))

    return ThreatFeedItemResponse(
        id=str(tp.id),
        riskLevel=tp.risk_level,
        title=tp.title,
        description=tp.description,
        category=tp.category,
        platformTag=tp.platform_tag,
        location=tp.location,
        reportCount=tp.report_count,
        viewCount=tp.view_count,
        timestamp=tp.created_at.isoformat() if tp.created_at else "",
        media=media_items,
        isBookmarked=is_bookmarked,
        isVerified=tp.is_verified,
    )


def _threat_to_detail(tp: ThreatPost, is_bookmarked: bool = False) -> ThreatDetailResponse:
    """Convert ThreatPost model to RFC full detail response."""
    base = _threat_to_item(tp, is_bookmarked)

    reported_by = None
    if tp.reported_by:
        reported_by = ThreatReportedBy(**tp.reported_by)

    example_content = None
    if tp.example_content:
        example_content = ThreatExampleContent(**tp.example_content)

    return ThreatDetailResponse(
        **base.model_dump(),
        reportedBy=reported_by,
        whatIsHappening=tp.what_is_happening,
        exampleContent=example_content,
        safetyTips=tp.safety_tips or [],
    )


# ---------------------------------------------------------------------------
# §6.1 Get Threat Feed List
# ---------------------------------------------------------------------------
@router.get("", response_model=ThreatFeedListResponse)
async def get_feed(
    tab: str = Query("for_you", description="for_you | trending | latest | nearby"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search query"),
    location: Optional[str] = Query(None, description="Filter by location"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated threat feed with filters."""
    query = select(ThreatPost).where(ThreatPost.is_published == True)

    # Category filter
    if category and category != "all":
        query = query.where(ThreatPost.category.ilike(f"%{category}%"))

    # Search
    if search:
        query = query.where(
            ThreatPost.title.ilike(f"%{search}%") |
            ThreatPost.description.ilike(f"%{search}%")
        )

    # Location filter
    if location:
        query = query.where(ThreatPost.location.ilike(f"%{location}%"))

    # Tab sorting
    if tab == "trending":
        query = query.order_by(ThreatPost.report_count.desc(), ThreatPost.created_at.desc())
    elif tab == "latest":
        query = query.order_by(ThreatPost.created_at.desc())
    else:
        query = query.order_by(ThreatPost.is_featured.desc(), ThreatPost.created_at.desc())

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_q) or 0

    # Paginate
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    posts = result.scalars().all()

    # Check bookmarks
    bookmarked_ids = set()
    if user and posts:
        post_ids = [p.id for p in posts]
        bm_result = await db.execute(
            select(FeedBookmark.threat_post_id)
            .where(FeedBookmark.user_id == user.id)
            .where(FeedBookmark.threat_post_id.in_(post_ids))
        )
        bookmarked_ids = {row[0] for row in bm_result.all()}

    items = [
        _threat_to_item(tp, is_bookmarked=(tp.id in bookmarked_ids))
        for tp in posts
    ]

    return ThreatFeedListResponse(
        data=items,
        pagination=FeedPaginationResponse(
            page=page,
            limit=limit,
            total=total,
            hasNext=(page * limit) < total,
        ),
    )


# ---------------------------------------------------------------------------
# §5.3 Threat Feed Preview (Home Dashboard)
# ---------------------------------------------------------------------------
@router.get("/preview")
async def get_feed_preview(
    limit: int = Query(2, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
):
    """Get top threat feed items for home dashboard preview."""
    query = (
        select(ThreatPost)
        .where(ThreatPost.is_published == True)
        .order_by(ThreatPost.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    posts = result.scalars().all()

    previews = []
    for tp in posts:
        # Calculate a human-readable timeAgo
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        diff = now - tp.created_at.replace(tzinfo=timezone.utc) if tp.created_at else None
        if diff:
            minutes = int(diff.total_seconds() / 60)
            if minutes < 60:
                time_ago = f"{minutes}m ago"
            elif minutes < 1440:
                time_ago = f"{minutes // 60}h ago"
            else:
                time_ago = f"{minutes // 1440}d ago"
        else:
            time_ago = ""

        # Icon type mapping
        icon_map = {
            "Banking": "mail",
            "Phishing": "link",
            "Fraud": "alert-circle",
            "Voice AI": "mic",
            "Deepfake": "videocam",
        }

        previews.append(ThreatPreviewItem(
            id=str(tp.id),
            riskLevel=tp.risk_level,
            title=tp.title,
            description=tp.description,
            location=tp.location,
            timeAgo=time_ago,
            type=tp.platform_tag or tp.category.lower() if tp.category else "",
            iconType=icon_map.get(tp.category, "alert-circle"),
            verifiedCount=tp.report_count,
        ))

    return previews


# ---------------------------------------------------------------------------
# §7.2 Get Threat Detail Dossier
# ---------------------------------------------------------------------------
@router.get("/{threat_id}", response_model=ThreatDetailResponse)
async def get_threat_detail(
    threat_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full threat incident dossier."""
    try:
        tp_uuid = UUID(threat_id)
    except (ValueError, TypeError):
        raise NotFoundError("Threat post", threat_id)

    result = await db.execute(
        select(ThreatPost)
        .where(ThreatPost.id == tp_uuid)
        .where(ThreatPost.is_published == True)
    )
    tp = result.scalar_one_or_none()
    if not tp:
        raise NotFoundError("Threat post", threat_id)

    # Increment view count
    tp.view_count += 1
    await db.flush()

    # Check bookmark
    is_bookmarked = False
    if user:
        bm_result = await db.execute(
            select(FeedBookmark)
            .where(FeedBookmark.user_id == user.id)
            .where(FeedBookmark.threat_post_id == tp.id)
        )
        is_bookmarked = bm_result.scalar_one_or_none() is not None

    return _threat_to_detail(tp, is_bookmarked=is_bookmarked)


# ---------------------------------------------------------------------------
# §6.2 Toggle Feed Bookmark
# ---------------------------------------------------------------------------
@router.post("/{threat_id}/bookmark", response_model=FeedBookmarkResponse)
async def toggle_feed_bookmark(
    threat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle bookmark on a threat feed post."""
    try:
        tp_uuid = UUID(threat_id)
    except (ValueError, TypeError):
        raise NotFoundError("Threat post", threat_id)

    # Verify post exists
    tp_result = await db.execute(
        select(ThreatPost).where(ThreatPost.id == tp_uuid)
    )
    if not tp_result.scalar_one_or_none():
        raise NotFoundError("Threat post", threat_id)

    # Toggle bookmark
    bm_result = await db.execute(
        select(FeedBookmark)
        .where(FeedBookmark.user_id == user.id)
        .where(FeedBookmark.threat_post_id == tp_uuid)
    )
    existing = bm_result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        is_bookmarked = False
    else:
        bookmark = FeedBookmark(user_id=user.id, threat_post_id=tp_uuid)
        db.add(bookmark)
        is_bookmarked = True

    await db.flush()
    return FeedBookmarkResponse(threatId=threat_id, isBookmarked=is_bookmarked)
