"""
Detection & Scan schemas — RFC §9 AI Detection, §10 Scan History.

Key differences from old schemas:
- riskLevel (HIGH|MEDIUM|LOW|SAFE) instead of verdict (Likely Scam|...)
- heroTitle, heroSubtitle for result screen
- reasons[] instead of red_flags[]
- recommendedActions[] instead of recommended_actions[]
- isBookmarked for bookmark state
- displayType, snippet for history display
- Unified 'mode' (text|email|image|video|audio) instead of separate endpoints
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class ScanMode(str, Enum):
    """RFC §9.1 — 5 user-facing scan modes."""
    TEXT = "text"
    EMAIL = "email"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class RiskLevel(str, Enum):
    """RFC §19.1 — Risk classification levels."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SAFE = "SAFE"


# ---------------------------------------------------------------------------
# §9.3 Submit Content for AI Scan Analysis
# ---------------------------------------------------------------------------
class ScanAnalyzeRequest(BaseSchema):
    """
    POST /api/v1/detect/analyze — RFC §9.3

    For text/email: send mode + content as JSON.
    For image/video/audio: send as multipart/form-data (handled at route level).
    """
    mode: ScanMode
    content: Optional[str] = Field(None, max_length=5000)
    # content is required for text/email modes, optional for file modes


class ScanResultResponse(BaseSchema):
    """
    RFC §19.1 — Detection Analysis Result Entity.

    This is the response for both:
    - POST /api/v1/detect/analyze (new scan)
    - GET /api/v1/detect/history/{scanId} (historical result)
    """
    id: str
    type: str  # text | email | image | video | audio
    displayType: str  # "Phishing SMS", "Voice Note", "Deepfake Video"
    title: str  # "Suspicious Text Message"
    snippet: str  # Content snippet or filename
    riskLevel: str  # HIGH | MEDIUM | LOW | SAFE
    confidence: int  # 0-100
    timestamp: str  # ISO-8601 UTC
    heroTitle: str  # "Threat Detected!" | "Suspicious Content" | "Looks Safe"
    heroSubtitle: str  # Explanatory guidance summary
    reasons: List[str] = []  # Risk indicator strings
    recommendedActions: List[str] = []  # Safe next-step actions
    isReportEligible: bool = False  # True if HIGH or MEDIUM risk
    isBookmarked: bool = False  # User bookmark state


# ---------------------------------------------------------------------------
# §10.1 Get Scan History List
# ---------------------------------------------------------------------------
class ScanHistoryStatsResponse(BaseSchema):
    """Summary counters for scan history header."""
    totalScans: int = 0
    totalThreats: int = 0


class ScanHistoryListResponse(BaseSchema):
    """
    GET /api/v1/detect/history — RFC §10.1

    Paginated list with summary stats.
    """
    stats: ScanHistoryStatsResponse
    scans: List[ScanResultResponse] = []
    pagination: dict = {}
    # {"page": 1, "limit": 20, "total": 47, "hasNext": true}


# ---------------------------------------------------------------------------
# §10.3 Toggle Scan Bookmark
# ---------------------------------------------------------------------------
class ScanBookmarkResponse(BaseSchema):
    """POST /api/v1/detect/history/{scanId}/bookmark — RFC §10.3"""
    scanId: str
    isBookmarked: bool


# ---------------------------------------------------------------------------
# Legacy schemas (kept for backward compatibility with existing code)
# ---------------------------------------------------------------------------
class DetectionType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"


class VerdictType(str, Enum):
    LIKELY_SCAM = "Likely Scam"
    SUSPICIOUS = "Suspicious"
    LIKELY_SAFE = "Likely Safe"


class TextDetectionRequest(BaseSchema):
    """Legacy text detection request."""
    content: str = Field(..., min_length=10, max_length=10000)


class AudioDetectionRequest(BaseSchema):
    """Legacy audio detection request."""
    media_url: str
    transcript: Optional[str] = None


class VideoDetectionRequest(BaseSchema):
    """Legacy video detection request."""
    media_url: str
    transcript: Optional[str] = None


class DetectionResponse(BaseSchema):
    """Legacy detection response."""
    id: UUID
    detection_type: DetectionType
    verdict: VerdictType
    confidence_score: int = Field(ge=0, le=100)
    scam_category: Optional[str] = None
    red_flags: List[str] = []
    explanation: str
    recommended_actions: List[str] = []
    educational_tip: str
    created_at: datetime
    remaining_detections: Optional[int] = None


class DetectionHistoryResponse(BaseSchema):
    """Legacy detection history item."""
    id: UUID
    detection_type: DetectionType
    verdict: VerdictType
    confidence_score: int
    scam_category: Optional[str] = None
    input_preview: Optional[str] = None
    created_at: datetime


class DetectionListResponse(BaseSchema):
    """Legacy paginated detection history."""
    items: List[DetectionHistoryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
