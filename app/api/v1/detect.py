"""
Detection API endpoints — RFC §9 AI Detection, §10 Scan History.

POST /api/v1/detect/analyze              — §9.3 Submit Content for AI Scan
GET  /api/v1/detect/history              — §10.1 Get Scan History List
GET  /api/v1/detect/history/{scanId}     — §10.2 Get Scan Result Detail
POST /api/v1/detect/history/{scanId}/bookmark — §10.3 Toggle Bookmark
"""
import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError, RateLimitExceededError
from app.core.logging import get_logger
from app.models.user import User
from app.models.detection import Detection, ScamCategory
from app.models.scan_bookmark import ScanBookmark
from app.schemas.detection import (
    ScanAnalyzeRequest,
    ScanResultResponse,
    ScanHistoryListResponse,
    ScanHistoryStatsResponse,
    ScanBookmarkResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/detect", tags=["Detection"])


# ---------------------------------------------------------------------------
# Helper: Convert Detection model → RFC ScanResultResponse
# ---------------------------------------------------------------------------
def _detection_to_scan_result(
    detection: Detection,
    is_bookmarked: bool = False,
) -> ScanResultResponse:
    """Map DB detection record to RFC-compliant scan result shape."""
    # Map verdict → riskLevel
    verdict_map = {
        "Likely Scam": "HIGH",
        "Suspicious": "MEDIUM",
        "Likely Safe": "SAFE",
    }
    risk_level = verdict_map.get(detection.verdict, "LOW")

    # Generate hero text based on risk
    hero_map = {
        "HIGH": ("Threat Detected!", "This content is likely a scam and may steal your data or money."),
        "MEDIUM": ("Suspicious Content", "This content exhibits deceptive patterns. Proceed with caution."),
        "LOW": ("Low Risk", "Some minor indicators found but overall risk is low."),
        "SAFE": ("Looks Safe", "We didn't find any major threats in this content."),
    }
    hero_title, hero_subtitle = hero_map.get(risk_level, hero_map["LOW"])

    # If AI provided a specific explanation, use it
    if detection.explanation:
        hero_subtitle = detection.explanation

    # Map detection_type → displayType
    display_map = {
        "text": "Text Message",
        "email": "Email Analysis",
        "image": "Image Analysis",
        "video": "Video Analysis",
        "audio": "Voice Note",
    }
    display_type = display_map.get(detection.detection_type, "Analysis")
    if risk_level == "HIGH" and detection.detection_type == "text":
        display_type = "Phishing SMS"

    # Snippet
    snippet = ""
    if detection.input_content:
        snippet = f'"{detection.input_content[:80]}..."' if len(detection.input_content) > 80 else f'"{detection.input_content}"'
    elif detection.media_url:
        snippet = detection.media_url.split("/")[-1] if "/" in detection.media_url else detection.media_url

    return ScanResultResponse(
        id=str(detection.id),
        type=detection.detection_type,
        displayType=display_type,
        title=f"{display_type} Scan",
        snippet=snippet,
        riskLevel=risk_level,
        confidence=detection.confidence_score,
        timestamp=detection.created_at.isoformat() if detection.created_at else "",
        heroTitle=hero_title,
        heroSubtitle=hero_subtitle,
        reasons=detection.red_flags or [],
        recommendedActions=detection.recommended_actions or [],
        isReportEligible=risk_level in ("HIGH", "MEDIUM"),
        isBookmarked=is_bookmarked,
    )


# ---------------------------------------------------------------------------
# §9.3 Submit Content for AI Scan Analysis
# ---------------------------------------------------------------------------
@router.post("/analyze", response_model=ScanResultResponse)
async def analyze_content(
    mode: str = Form("text"),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified scan analysis endpoint.

    - text/email: Send mode + content as form fields
    - image/video/audio: Send mode + file as multipart upload
    """
    from app.services.detection.gemini_client import gemini_client

    # Validate input
    if mode in ("text", "email"):
        if not content or len(content.strip()) < 5:
            from app.core.exceptions import ValidationError
            raise ValidationError("Content is required for text/email scan", field="content")
        input_content = content.strip()
        input_hash = hashlib.sha256(input_content.encode()).hexdigest()
        media_url = None
    elif mode in ("image", "video", "audio"):
        if not file:
            from app.core.exceptions import ValidationError
            raise ValidationError(f"File upload is required for {mode} scan", field="file")
        # Read file for processing
        file_bytes = await file.read()
        input_content = None
        input_hash = hashlib.sha256(file_bytes).hexdigest()
        media_url = None  # TODO: Upload to R2 and get URL
    else:
        from app.core.exceptions import ValidationError
        raise ValidationError(f"Unsupported scan mode: {mode}", field="mode")

    # AI analysis
    if mode in ("text", "email"):
        result = await gemini_client.analyze_text(input_content)
    elif mode == "image":
        # Use SightEngine for image analysis
        try:
            from app.services.detection.sightengine_client import sightengine_client
            result = await sightengine_client.analyze_image(file_bytes, file.filename)
        except ImportError:
            # Fallback to Gemini if SightEngine not available
            result = await gemini_client.analyze_text(f"[Image file: {file.filename}]")
    else:
        # audio/video: use Gemini with transcript fallback
        result = await gemini_client.analyze_text(
            input_content or f"[{mode} file uploaded: {file.filename if file else 'unknown'}]"
        )

    # Find category
    category_id = None
    if result.get("scam_category"):
        cat_result = await db.execute(
            select(ScamCategory).where(ScamCategory.name == result["scam_category"])
        )
        cat_obj = cat_result.scalar_one_or_none()
        if cat_obj:
            category_id = cat_obj.id

    # Save detection
    detection = Detection(
        user_id=user.id,
        detection_type=mode,
        input_hash=input_hash,
        input_content=input_content,
        media_url=media_url,
        verdict=result.get("verdict", "Likely Safe"),
        confidence_score=result.get("confidence_score", 50),
        category_id=category_id,
        red_flags=result.get("red_flags", []),
        explanation=result.get("explanation"),
        recommended_actions=result.get("recommended_actions", []),
        educational_tip=result.get("educational_tip"),
        raw_ai_response=result.get("raw_response"),
        ai_provider=result.get("ai_provider", "gemini"),
        processing_time_ms=result.get("processing_time_ms"),
    )
    db.add(detection)
    await db.flush()

    logger.info(f"Scan completed: {detection.id} mode={mode} verdict={detection.verdict}")
    return _detection_to_scan_result(detection)


# ---------------------------------------------------------------------------
# §10.1 Get Scan History List
# ---------------------------------------------------------------------------
@router.get("/history", response_model=ScanHistoryListResponse)
async def get_scan_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    type: Optional[str] = Query(None),
    riskLevel: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated scan history with stats summary."""
    query = select(Detection).where(Detection.user_id == user.id)

    # Filters
    if type:
        query = query.where(Detection.detection_type == type)
    if riskLevel:
        verdict_map = {"HIGH": "Likely Scam", "MEDIUM": "Suspicious", "SAFE": "Likely Safe"}
        verdict = verdict_map.get(riskLevel)
        if verdict:
            query = query.where(Detection.verdict == verdict)

    # Count total
    count_q = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_q) or 0

    # Count threats
    threats_q = select(func.count()).select_from(
        select(Detection)
        .where(Detection.user_id == user.id)
        .where(Detection.verdict.in_(["Likely Scam", "Suspicious"]))
        .subquery()
    )
    total_threats = await db.scalar(threats_q) or 0

    # Fetch page
    query = query.order_by(Detection.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    detections = result.scalars().all()

    # Check bookmarks
    if detections:
        det_ids = [d.id for d in detections]
        bm_result = await db.execute(
            select(ScanBookmark.detection_id)
            .where(ScanBookmark.user_id == user.id)
            .where(ScanBookmark.detection_id.in_(det_ids))
        )
        bookmarked_ids = {row[0] for row in bm_result.all()}
    else:
        bookmarked_ids = set()

    scans = [
        _detection_to_scan_result(d, is_bookmarked=(d.id in bookmarked_ids))
        for d in detections
    ]

    return ScanHistoryListResponse(
        stats=ScanHistoryStatsResponse(totalScans=total, totalThreats=total_threats),
        scans=scans,
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "hasNext": (page * limit) < total,
        },
    )


# ---------------------------------------------------------------------------
# §10.2 Get Scan Result Detail
# ---------------------------------------------------------------------------
@router.get("/history/{scan_id}", response_model=ScanResultResponse)
async def get_scan_detail(
    scan_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed scan result by ID."""
    try:
        detection_uuid = UUID(scan_id)
    except (ValueError, TypeError):
        raise NotFoundError("Scan result", scan_id)

    result = await db.execute(
        select(Detection)
        .where(Detection.id == detection_uuid)
        .where(Detection.user_id == user.id)
    )
    detection = result.scalar_one_or_none()
    if not detection:
        raise NotFoundError("Scan result", scan_id)

    # Check bookmark
    bm_result = await db.execute(
        select(ScanBookmark)
        .where(ScanBookmark.user_id == user.id)
        .where(ScanBookmark.detection_id == detection.id)
    )
    is_bookmarked = bm_result.scalar_one_or_none() is not None

    return _detection_to_scan_result(detection, is_bookmarked=is_bookmarked)


# ---------------------------------------------------------------------------
# §10.3 Toggle Scan Result Bookmark
# ---------------------------------------------------------------------------
@router.post("/history/{scan_id}/bookmark", response_model=ScanBookmarkResponse)
async def toggle_scan_bookmark(
    scan_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle bookmark on a scan result."""
    try:
        detection_uuid = UUID(scan_id)
    except (ValueError, TypeError):
        raise NotFoundError("Scan result", scan_id)

    # Verify detection belongs to user
    det_result = await db.execute(
        select(Detection)
        .where(Detection.id == detection_uuid)
        .where(Detection.user_id == user.id)
    )
    if not det_result.scalar_one_or_none():
        raise NotFoundError("Scan result", scan_id)

    # Check existing bookmark
    bm_result = await db.execute(
        select(ScanBookmark)
        .where(ScanBookmark.user_id == user.id)
        .where(ScanBookmark.detection_id == detection_uuid)
    )
    existing = bm_result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        is_bookmarked = False
    else:
        bookmark = ScanBookmark(user_id=user.id, detection_id=detection_uuid)
        db.add(bookmark)
        is_bookmarked = True

    await db.flush()
    return ScanBookmarkResponse(scanId=scan_id, isBookmarked=is_bookmarked)
