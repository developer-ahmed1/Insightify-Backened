"""
Scam detection endpoints.
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user, get_detection_service
from app.models.user import User
from app.schemas.detection import (
    TextDetectionRequest, AudioDetectionRequest, VideoDetectionRequest,
    DetectionResponse
)
from app.services.detection.detection_service import DetectionService

router = APIRouter()


@router.post("/text", response_model=DetectionResponse)
async def detect_text_scam(
    request: TextDetectionRequest,
    user: User = Depends(get_current_active_user),
    service: DetectionService = Depends(get_detection_service),
):
    """
    Analyze text for scam indicators.
    
    Free users: 10 detections/day
    Premium users: 100 detections/day
    """
    return await service.detect_text(user, request)


@router.post("/audio", response_model=DetectionResponse)
async def detect_audio_scam(
    request: AudioDetectionRequest,
    user: User = Depends(get_current_active_user),
    service: DetectionService = Depends(get_detection_service),
):
    """
    Analyze audio for scam indicators.
    
    Requires uploaded audio file URL.
    Free users: 3 detections/day
    Premium users: 50 detections/day
    """
    return await service.detect_audio(user, request)


@router.post("/video", response_model=DetectionResponse)
async def detect_video_scam(
    request: VideoDetectionRequest,
    user: User = Depends(get_current_active_user),
    service: DetectionService = Depends(get_detection_service),
):
    """
    Analyze video for scam indicators.
    
    Requires uploaded video file URL.
    Free users: Not available (0/day)
    Premium users: 20 detections/day
    """
    return await service.detect_video(user, request)
