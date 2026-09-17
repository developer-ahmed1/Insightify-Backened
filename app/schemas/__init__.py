"""
Pydantic schemas for request/response validation.
"""
from app.schemas.common import BaseSchema, PaginatedResponse, MessageResponse
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserProfile,
    StreakResponse, UserLimitsResponse
)
from app.schemas.detection import (
    TextDetectionRequest, AudioDetectionRequest, VideoDetectionRequest,
    DetectionResponse, DetectionHistoryResponse, DetectionListResponse
)
from app.schemas.community import (
    PostCreate, PostUpdate, PostResponse, PostListResponse,
    CommentCreate, CommentResponse, ReactionCreate, ReportCreate
)
from app.schemas.gamification import (
    BadgeResponse, UserBadgeResponse, LeaderboardEntry,
    QuizResponse, QuizQuestionResponse, QuizAttemptCreate, QuizAttemptResponse
)
from app.schemas.education import (
    ScamCategoryResponse, EducationalContentResponse
)
from app.schemas.monetization import (
    SubscriptionPlanResponse, SubscriptionResponse
)

__all__ = [
    # Common
    "BaseSchema",
    "PaginatedResponse",
    "MessageResponse",
    # User
    "UserCreate",
    "UserUpdate", 
    "UserResponse",
    "UserProfile",
    "StreakResponse",
    "UserLimitsResponse",
    # Detection
    "TextDetectionRequest",
    "AudioDetectionRequest",
    "VideoDetectionRequest",
    "DetectionResponse",
    "DetectionHistoryResponse",
    "DetectionListResponse",
    # Community
    "PostCreate",
    "PostUpdate",
    "PostResponse",
    "PostListResponse",
    "CommentCreate",
    "CommentResponse",
    "ReactionCreate",
    "ReportCreate",
    # Gamification
    "BadgeResponse",
    "UserBadgeResponse",
    "LeaderboardEntry",
    "QuizResponse",
    "QuizQuestionResponse",
    "QuizAttemptCreate",
    "QuizAttemptResponse",
    # Education
    "ScamCategoryResponse",
    "EducationalContentResponse",
    # Monetization
    "SubscriptionPlanResponse",
    "SubscriptionResponse",
]
