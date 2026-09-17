"""
User and profile models.

RFC §3 — User Profile fields: id, name, username, title, bio, email, avatar,
level, xp, nextLevelXp, rank, stats (safetyScore, threatsPrevented, scansCount,
reportsCount, verificationsCount).
"""
from datetime import datetime, date
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Integer, String, Text, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class User(Base, TimestampMixin, SoftDeleteMixin):
    """User model with JWT auth support."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Authentication (JWT-based, replaces Firebase)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Null for Google-only users
    google_uid = Column(String(128), unique=True, nullable=True, index=True)

    # Profile fields per RFC §3
    name = Column(String(100), nullable=True)  # RFC: fullName / name
    username = Column(String(50), unique=True, nullable=True, index=True)
    title = Column(String(100), nullable=True)  # e.g. "AI Awareness Champion"
    bio = Column(Text, nullable=True)
    avatar = Column(String(500), nullable=True)  # RFC uses "avatar" not "avatar_url"
    display_name = Column(String(100), nullable=True)  # Legacy, kept for compat

    # Gamification
    xp = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)

    # Subscription
    is_premium = Column(Boolean, default=False, nullable=False)
    subscription_tier = Column(String(50), default="free", nullable=False)
    show_ads = Column(Boolean, default=True, nullable=False)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # Password reset
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)

    # Settings (RFC §4 — server-persisted preferences)
    settings = Column(JSONB, default=lambda: {
        "profilePublic": True,
        "showOnLeaderboard": True,
        "anonymousReports": False,
        "notifications": {
            "enabled": True,
            "scamAlerts": True,
            "achievements": True,
            "leaderboardUpdates": True,
        }
    }, nullable=False)

    # Legacy settings columns (kept for backward compat)
    email_notifications = Column(Boolean, default=True, nullable=False)
    push_notifications = Column(Boolean, default=True, nullable=False)

    # Relationships
    streak = relationship("UserStreak", back_populates="user", uselist=False)
    detections = relationship("Detection", back_populates="user")
    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    badges = relationship("UserBadge", back_populates="user")
    quiz_attempts = relationship("QuizAttempt", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    scan_bookmarks = relationship("ScanBookmark", back_populates="user")
    feed_bookmarks = relationship("FeedBookmark", back_populates="user")
    notifications = relationship("Notification", back_populates="user")

    __table_args__ = (
        Index("idx_users_xp", "xp"),
        Index("idx_users_level", "level"),
    )

    @property
    def next_level_xp(self) -> int:
        """Calculate XP required for next level."""
        return self.level * 200  # 200 XP per level

    @property
    def rank(self) -> Optional[int]:
        """Rank is computed by the service layer, not stored."""
        return None

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class UserStreak(Base, TimestampMixin):
    """User streak tracking for daily engagement."""

    __tablename__ = "user_streaks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    last_activity_date = Column(Date, nullable=True)

    # Relationship
    user = relationship("User", back_populates="streak")

    def update_streak(self) -> int:
        """
        Update streak based on current date.
        Returns XP bonus if milestone reached.
        """
        today = date.today()
        xp_bonus = 0

        if self.last_activity_date is None:
            # First activity
            self.current_streak = 1
        elif self.last_activity_date == today:
            # Already counted today
            return 0
        elif (today - self.last_activity_date).days == 1:
            # Consecutive day
            self.current_streak += 1

            # Milestone bonuses
            milestones = {7: 70, 14: 140, 30: 300, 60: 600, 100: 1000}
            if self.current_streak in milestones:
                xp_bonus = milestones[self.current_streak]
        else:
            # Streak broken
            self.current_streak = 1

        # Update longest streak
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak

        self.last_activity_date = today
        return xp_bonus

    def __repr__(self) -> str:
        return f"<UserStreak user_id={self.user_id} current={self.current_streak}>"
