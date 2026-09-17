"""
Database models — all models registered here for Alembic discovery.
"""
from app.models.base import Base, TimestampMixin, SoftDeleteMixin
from app.models.user import User, UserStreak
from app.models.detection import Detection, ScamCategory
from app.models.community import Post, Comment, Reaction, Report, ModerationLog
from app.models.gamification import (
    Badge,
    UserBadge,
    XPRule,
    Quiz,
    QuizQuestion,
    QuizAttempt
)
from app.models.education import EducationalContent
from app.models.monetization import SubscriptionPlan, Subscription
from app.models.threat_post import ThreatPost, FeedBookmark
from app.models.scan_bookmark import ScanBookmark
from app.models.notification import Notification
from app.models.daily_tip import DailySafetyTip
from app.models.daily_challenge import DailyChallenge

__all__ = [
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    # User
    "User",
    "UserStreak",
    # Detection
    "Detection",
    "ScamCategory",
    "ScanBookmark",
    # Community (legacy)
    "Post",
    "Comment",
    "Reaction",
    "Report",
    "ModerationLog",
    # Gamification
    "Badge",
    "UserBadge",
    "XPRule",
    "Quiz",
    "QuizQuestion",
    "QuizAttempt",
    # Education
    "EducationalContent",
    # Monetization
    "SubscriptionPlan",
    "Subscription",
    # Threat Feed (RFC §6-7)
    "ThreatPost",
    "FeedBookmark",
    # Notifications (RFC §15)
    "Notification",
    # Daily Tips & Challenges (RFC §5.4, §11.3)
    "DailySafetyTip",
    "DailyChallenge",
]
