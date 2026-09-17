"""
Detection service for scam analysis.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.rate_limiter import rate_limiter
from app.core.exceptions import RateLimitExceededError
from app.models.user import User
from app.models.detection import Detection, ScamCategory
from app.schemas.detection import (
    DetectionType, VerdictType,
    TextDetectionRequest, AudioDetectionRequest, VideoDetectionRequest,
    DetectionResponse, DetectionHistoryResponse
)
from app.services.detection.gemini_client import gemini_client

logger = get_logger(__name__)


class DetectionService:
    """Service for scam detection."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai = gemini_client

    async def detect_text(
        self,
        user: User,
        request: TextDetectionRequest,
    ) -> DetectionResponse:
        """
        Analyze text for scam indicators.
        """
        # Check rate limit
        remaining = await rate_limiter.check_or_raise(
            str(user.id),
            "text_detection",
            user.is_premium,
        )

        # Analyze with AI
        result = await self.ai.analyze_text(request.content)

        # Save detection
        detection = await self._save_detection(
            user_id=user.id,
            detection_type=DetectionType.TEXT,
            input_content=request.content,
            input_hash=result["input_hash"],
            result=result,
        )

        return self._to_response(detection, remaining)

    async def detect_audio(
        self,
        user: User,
        request: AudioDetectionRequest,
    ) -> DetectionResponse:
        """Analyze audio for scam indicators."""
        remaining = await rate_limiter.check_or_raise(
            str(user.id),
            "audio_detection",
            user.is_premium,
        )

        result = await self.ai.analyze_audio(
            request.media_url,
            request.transcript,
        )

        detection = await self._save_detection(
            user_id=user.id,
            detection_type=DetectionType.AUDIO,
            input_content=request.transcript,
            input_hash=result["input_hash"],
            media_url=request.media_url,
            result=result,
        )

        return self._to_response(detection, remaining)

    async def detect_video(
        self,
        user: User,
        request: VideoDetectionRequest,
    ) -> DetectionResponse:
        """Analyze video for scam indicators."""
        remaining = await rate_limiter.check_or_raise(
            str(user.id),
            "video_detection",
            user.is_premium,
        )

        result = await self.ai.analyze_video(
            request.media_url,
            request.transcript,
        )

        detection = await self._save_detection(
            user_id=user.id,
            detection_type=DetectionType.VIDEO,
            input_content=request.transcript,
            input_hash=result["input_hash"],
            media_url=request.media_url,
            result=result,
        )

        return self._to_response(detection, remaining)

    async def _save_detection(
        self,
        user_id: UUID,
        detection_type: DetectionType,
        input_hash: str,
        result: dict,
        input_content: Optional[str] = None,
        media_url: Optional[str] = None,
    ) -> Detection:
        """Save detection result to database."""
        # Try to find category
        category_id = None
        if result.get("scam_category"):
            category = await self.db.execute(
                select(ScamCategory)
                .where(ScamCategory.name == result["scam_category"])
            )
            category_obj = category.scalar_one_or_none()
            if category_obj:
                category_id = category_obj.id

        detection = Detection(
            user_id=user_id,
            detection_type=detection_type.value,
            input_hash=input_hash,
            input_content=input_content,
            media_url=media_url,
            verdict=result["verdict"],
            confidence_score=result["confidence_score"],
            category_id=category_id,
            red_flags=result.get("red_flags", []),
            explanation=result.get("explanation"),
            recommended_actions=result.get("recommended_actions", []),
            educational_tip=result.get("educational_tip"),
            raw_ai_response=result.get("raw_response"),
            ai_provider=result.get("ai_provider", "hive"),
            processing_time_ms=result.get("processing_time_ms"),
        )

        self.db.add(detection)
        await self.db.flush()

        logger.info(
            f"Detection saved: {detection.id} type={detection_type} "
            f"verdict={result['verdict']}"
        )

        return detection

    def _to_response(self, detection: Detection, remaining: int) -> DetectionResponse:
        """Convert detection model to response schema."""
        return DetectionResponse(
            id=detection.id,
            detection_type=DetectionType(detection.detection_type),
            verdict=VerdictType(detection.verdict),
            confidence_score=detection.confidence_score,
            scam_category=detection.category.name if detection.category else None,
            red_flags=detection.red_flags or [],
            explanation=detection.explanation or "",
            recommended_actions=detection.recommended_actions or [],
            educational_tip=detection.educational_tip or "",
            created_at=detection.created_at,
            remaining_detections=remaining,
        )

    # History methods
    async def get_history(
        self,
        user_id: UUID,
        detection_type: Optional[str] = None,
        verdict: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DetectionHistoryResponse], int]:
        """Get user's detection history."""
        from sqlalchemy import func

        query = (
            select(Detection)
            .where(Detection.user_id == user_id)
            .order_by(Detection.created_at.desc())
        )

        # Apply filters
        if detection_type:
            query = query.where(Detection.detection_type == detection_type)
        if verdict:
            query = query.where(Detection.verdict == verdict)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        detections = result.scalars().all()

        items = [
            DetectionHistoryResponse(
                id=d.id,
                detection_type=DetectionType(d.detection_type),
                verdict=VerdictType(d.verdict),
                confidence_score=d.confidence_score,
                scam_category=d.category.name if d.category else None,
                input_preview=d.input_content[:100] if d.input_content else None,
                created_at=d.created_at,
            )
            for d in detections
        ]

        return items, total

    async def get_detection(self, detection_id: UUID, user_id: UUID) -> Optional[Detection]:
        """Get single detection by ID."""
        result = await self.db.execute(
            select(Detection)
            .where(Detection.id == detection_id)
            .where(Detection.user_id == user_id)
        )
        return result.scalar_one_or_none()
