"""
Detection history endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_active_user, get_detection_service
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.detection import (
    DetectionResponse, DetectionListResponse, DetectionHistoryResponse
)
from app.services.detection.detection_service import DetectionService

router = APIRouter()


@router.get("", response_model=DetectionListResponse)
async def get_detection_history(
    detection_type: Optional[str] = Query(None, description="Filter by type: text, audio, video"),
    verdict: Optional[str] = Query(None, description="Filter by verdict"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_active_user),
    service: DetectionService = Depends(get_detection_service),
):
    """Get user's detection history with optional filters."""
    items, total = await service.get_history(
        user_id=user.id,
        detection_type=detection_type,
        verdict=verdict,
        page=page,
        page_size=page_size,
    )
    
    return DetectionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
    )


@router.get("/{detection_id}", response_model=DetectionResponse)
async def get_detection_detail(
    detection_id: UUID,
    user: User = Depends(get_current_active_user),
    service: DetectionService = Depends(get_detection_service),
):
    """Get details of a specific detection."""
    detection = await service.get_detection(detection_id, user.id)
    if not detection:
        raise NotFoundError("Detection", str(detection_id))
    
    return DetectionResponse(
        id=detection.id,
        detection_type=detection.detection_type,
        verdict=detection.verdict,
        confidence_score=detection.confidence_score,
        scam_category=detection.category.name if detection.category else None,
        red_flags=detection.red_flags or [],
        explanation=detection.explanation or "",
        recommended_actions=detection.recommended_actions or [],
        educational_tip=detection.educational_tip or "",
        created_at=detection.created_at,
    )
