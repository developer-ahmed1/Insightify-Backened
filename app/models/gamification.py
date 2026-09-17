"""
Gamification models: badges, XP rules, quizzes.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, Text, 
    Boolean, Float, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Badge(Base, TimestampMixin):
    """Badge that users can earn."""

    __tablename__ = "badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    icon_url = Column(String(500), nullable=True)
    category = Column(String(50), nullable=False)
    # detection, community, education, streak, special
    
    xp_reward = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)  # Secret badges

    # Badge criteria (evaluated by gamification service)
    criteria = Column(JSONB, nullable=True)
    # Example: {"type": "count", "field": "detections", "threshold": 100}

    # Relationships
    user_badges = relationship("UserBadge", back_populates="badge")

    def __repr__(self) -> str:
        return f"<Badge {self.name}>"


class UserBadge(Base, TimestampMixin):
    """User's earned badges."""

    __tablename__ = "user_badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    badge_id = Column(
        UUID(as_uuid=True),
        ForeignKey("badges.id", ondelete="CASCADE"),
        nullable=False,
    )
    earned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_displayed = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="badges")
    badge = relationship("Badge", back_populates="user_badges")

    __table_args__ = (
        Index("idx_user_badges_unique", "user_id", "badge_id", unique=True),
    )


class XPRule(Base, TimestampMixin):
    """Configurable XP rules stored in database."""

    __tablename__ = "xp_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    action = Column(String(100), unique=True, nullable=False)
    # detection_text, detection_audio, post_created, comment_helpful, etc.
    
    description = Column(Text, nullable=True)
    base_xp = Column(Integer, nullable=False)
    premium_multiplier = Column(Float, default=1.5, nullable=False)
    
    # Limits
    daily_limit = Column(Integer, nullable=True)  # None = unlimited
    cooldown_minutes = Column(Integer, nullable=True)  # Cooldown between awards
    
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<XPRule {self.action}: {self.base_xp}xp>"


class Quiz(Base, TimestampMixin):
    """Educational quiz."""

    __tablename__ = "quizzes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scam_categories.id"),
        nullable=True,
    )
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    difficulty_level = Column(Integer, default=1, nullable=False)  # 1-5
    xp_reward = Column(Integer, default=50, nullable=False)
    time_limit_seconds = Column(Integer, nullable=True)  # Optional time limit
    
    is_active = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    
    # Stats (denormalized)
    total_attempts = Column(Integer, default=0, nullable=False)
    average_score = Column(Float, default=0.0, nullable=False)

    # Relationships
    category = relationship("ScamCategory", back_populates="quizzes")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="quiz")

    __table_args__ = (
        Index("idx_quizzes_difficulty", "difficulty_level"),
        Index("idx_quizzes_category", "category_id"),
    )

    def __repr__(self) -> str:
        return f"<Quiz {self.title}>"


class QuizQuestion(Base, TimestampMixin):
    """Question in a quiz."""

    __tablename__ = "quiz_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    quiz_id = Column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )

    question_type = Column(String(20), default="mcq", nullable=False)
    # mcq, true_false, image_identify
    
    question = Column(Text, nullable=False)
    media_url = Column(String(500), nullable=True)  # Image for visual questions
    
    options = Column(JSONB, nullable=False)  # List of options
    correct_answer = Column(String(200), nullable=False)
    explanation = Column(Text, nullable=True)  # Shown after answer
    
    order_index = Column(Integer, default=0, nullable=False)
    points = Column(Integer, default=10, nullable=False)

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")

    __table_args__ = (
        Index("idx_quiz_questions_order", "quiz_id", "order_index"),
    )

    def __repr__(self) -> str:
        return f"<QuizQuestion {self.id}>"


class QuizAttempt(Base, TimestampMixin):
    """User's quiz attempt record."""

    __tablename__ = "quiz_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_id = Column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Results
    score = Column(Integer, default=0, nullable=False)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, default=0, nullable=False)
    xp_earned = Column(Integer, default=0, nullable=False)
    
    # Answers stored for analysis
    answers = Column(JSONB, default=list)
    # [{"question_id": "...", "answer": "...", "is_correct": true, "time_ms": 1234}]
    
    time_taken_seconds = Column(Integer, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="quiz_attempts")
    quiz = relationship("Quiz", back_populates="attempts")

    __table_args__ = (
        Index("idx_quiz_attempts_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<QuizAttempt user={self.user_id} quiz={self.quiz_id}>"
