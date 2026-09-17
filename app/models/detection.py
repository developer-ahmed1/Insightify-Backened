"""
Scam detection models.
"""
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, Text, Boolean, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class ScamCategory(Base, TimestampMixin):
    """Scam category for classification."""

    __tablename__ = "scam_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    icon_url = Column(String(500), nullable=True)
    severity_level = Column(Integer, default=5, nullable=False)  # 1-10
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    detections = relationship("Detection", back_populates="category")
    educational_content = relationship("EducationalContent", back_populates="category")
    quizzes = relationship("Quiz", back_populates="category")

    def __repr__(self) -> str:
        return f"<ScamCategory {self.name}>"


class Detection(Base, TimestampMixin):
    """Scam detection record."""

    __tablename__ = "detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Detection type and input
    detection_type = Column(String(20), nullable=False)  # text, audio, video
    input_hash = Column(String(64), nullable=False, index=True)  # SHA256 hash for dedup
    input_content = Column(Text, nullable=True)  # Text content or transcript
    media_url = Column(String(500), nullable=True)  # URL if media was uploaded

    # Results
    verdict = Column(String(50), nullable=False)  # Likely Scam, Suspicious, Likely Safe
    confidence_score = Column(Integer, nullable=False)  # 0-100
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scam_categories.id"),
        nullable=True,
    )
    
    # Detailed analysis
    red_flags = Column(JSONB, default=list)
    explanation = Column(Text, nullable=True)
    recommended_actions = Column(JSONB, default=list)
    educational_tip = Column(Text, nullable=True)

    # Raw response for debugging/re-analysis
    raw_ai_response = Column(JSONB, nullable=True)
    ai_provider = Column(String(50), default="hive")  # Track which AI was used
    processing_time_ms = Column(Integer, nullable=True)

    # Relationships
    user = relationship("User", back_populates="detections")
    category = relationship("ScamCategory", back_populates="detections")
    bookmarks = relationship("ScanBookmark", back_populates="detection",
                             cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_detections_user_type", "user_id", "detection_type"),
        Index("idx_detections_user_verdict", "user_id", "verdict"),
        Index("idx_detections_hash", "input_hash"),
    )

    def __repr__(self) -> str:
        return f"<Detection {self.id} type={self.detection_type} verdict={self.verdict}>"

    @property
    def is_scam(self) -> bool:
        """Check if detection result is a scam."""
        return self.verdict == "Likely Scam"

    @property
    def is_suspicious(self) -> bool:
        """Check if detection result is suspicious."""
        return self.verdict in ("Likely Scam", "Suspicious")
