"""
Threat Feed schemas — RFC §6 Community Threat Feed, §7 Threat Feed Detail.
"""
from typing import List, Optional
from pydantic import Field
from app.schemas.common import BaseSchema


# ---------------------------------------------------------------------------
# §7.1 Media / Evidence Model
# ---------------------------------------------------------------------------
class ThreatMediaItem(BaseSchema):
    """Multimodal evidence item per RFC §7.1."""
    id: str
    type: str  # image | video | audio
    url: str
    thumbnailUrl: Optional[str] = None
    title: Optional[str] = None


class ThreatReportedBy(BaseSchema):
    """Who reported this threat."""
    name: str
    badge: Optional[str] = None
    role: Optional[str] = None


class ThreatExampleContent(BaseSchema):
    """Example scam content."""
    type: str
    prefix: str
    link: Optional[str] = None


# ---------------------------------------------------------------------------
# §6.1 Feed List Item
# ---------------------------------------------------------------------------
class ThreatFeedItemResponse(BaseSchema):
    """
    RFC §19.2 — ThreatFeedItem entity.
    Used in GET /api/v1/feed and GET /api/v1/feed/preview.
    """
    id: str
    riskLevel: str  # HIGH | MEDIUM | INFO
    title: str
    description: str
    category: str  # Banking | Phishing | Fraud | Voice AI | Deepfake
    platformTag: Optional[str] = None
    location: Optional[str] = None
    reportCount: int = 0
    viewCount: int = 0
    timestamp: str  # ISO-8601 UTC
    media: List[ThreatMediaItem] = []
    isBookmarked: bool = False
    isVerified: bool = False


# ---------------------------------------------------------------------------
# §6.1 Feed List (Paginated)
# ---------------------------------------------------------------------------
class FeedPaginationResponse(BaseSchema):
    """Pagination info."""
    page: int = 1
    limit: int = 10
    total: int = 0
    hasNext: bool = False


class ThreatFeedListResponse(BaseSchema):
    """GET /api/v1/feed — RFC §6.1"""
    data: List[ThreatFeedItemResponse] = []
    pagination: FeedPaginationResponse = FeedPaginationResponse()


# ---------------------------------------------------------------------------
# §7.2 Threat Detail Dossier (extended from list item)
# ---------------------------------------------------------------------------
class ThreatDetailResponse(ThreatFeedItemResponse):
    """
    GET /api/v1/feed/{threatId} — RFC §7.2

    Full threat incident dossier with evidence, example content, and safety tips.
    """
    reportedBy: Optional[ThreatReportedBy] = None
    whatIsHappening: Optional[str] = None
    exampleContent: Optional[ThreatExampleContent] = None
    safetyTips: List[str] = []


# ---------------------------------------------------------------------------
# §6.2 Bookmark
# ---------------------------------------------------------------------------
class FeedBookmarkResponse(BaseSchema):
    """POST /api/v1/feed/{threatId}/bookmark — RFC §6.2"""
    threatId: str
    isBookmarked: bool


# ---------------------------------------------------------------------------
# Admin: Create/Update Threat Post
# ---------------------------------------------------------------------------
class ThreatPostCreateRequest(BaseSchema):
    """Admin: Create a new threat post."""
    riskLevel: str = Field("MEDIUM", description="HIGH | MEDIUM | INFO")
    title: str = Field(..., max_length=300)
    description: str
    category: str
    platformTag: Optional[str] = None
    location: Optional[str] = None
    isVerified: bool = False
    isPublished: bool = False
    media: List[dict] = []
    reportedBy: Optional[dict] = None
    whatIsHappening: Optional[str] = None
    exampleContent: Optional[dict] = None
    safetyTips: List[str] = []


class ThreatPostUpdateRequest(BaseSchema):
    """Admin: Update a threat post."""
    riskLevel: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    platformTag: Optional[str] = None
    location: Optional[str] = None
    isVerified: Optional[bool] = None
    isPublished: Optional[bool] = None
    media: Optional[List[dict]] = None
    reportedBy: Optional[dict] = None
    whatIsHappening: Optional[str] = None
    exampleContent: Optional[dict] = None
    safetyTips: Optional[List[str]] = None
