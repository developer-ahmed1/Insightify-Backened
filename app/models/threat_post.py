"""
Threat Post model for the community threat feed.

RFC §6-7 — Threat Feed Item Entity with multimodal media.
Separate from the community Post model (user-generated content).
ThreatPosts are admin-curated threat intelligence records.
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


class ThreatPost(Base, TimestampMixin):
    """
    Admin-curated threat intelligence feed post.

    RFC §19.2 ThreatFeedItem entity:
    - riskLevel: HIGH | MEDIUM | INFO
    - category: Banking | Phishing | Fraud | Voice AI | Deepfake
    - platformTag: SMS | WhatsApp | Facebook | Voice AI
    - media[]: multimodal evidence array
    """

    __tablename__ = "threat_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Core fields per RFC §6.1
    risk_level = Column(String(20), nullable=False, default="MEDIUM")
    # HIGH | MEDIUM | INFO
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    # Banking | Phishing | Fraud | Voice AI | Deepfake
    platform_tag = Column(String(50), nullable=True)
    # SMS | WhatsApp | Facebook | Voice AI
    location = Column(String(100), nullable=True)
    # e.g. "Pakistan", "India", "Global"

    # Engagement counters
    report_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)

    # Verification
    is_verified = Column(Boolean, default=False, nullable=False)

    # Multimodal evidence — JSONB array per RFC §7.1
    # [{"id": "med_101", "type": "image", "url": "...", "thumbnailUrl": "...", "title": "..."}]
    media = Column(JSONB, default=list)

    # Detail dossier fields per RFC §7.2
    reported_by = Column(JSONB, nullable=True)
    # {"name": "...", "badge": "...", "role": "..."}
    what_is_happening = Column(Text, nullable=True)
    example_content = Column(JSONB, nullable=True)
    # {"type": "sms", "prefix": "...", "link": "..."}
    safety_tips = Column(JSONB, default=list)

    # Admin/moderation
    is_published = Column(Boolean, default=False, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    bookmarks = relationship("FeedBookmark", back_populates="threat_post",
                             cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_threat_posts_risk", "risk_level"),
        Index("idx_threat_posts_category", "category"),
        Index("idx_threat_posts_published", "is_published"),
        Index("idx_threat_posts_verified", "is_verified"),
        Index("idx_threat_posts_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ThreatPost {self.title[:40]}>"


class FeedBookmark(Base, TimestampMixin):
    """User bookmark on a threat feed post. RFC §6.2."""

    __tablename__ = "feed_bookmarks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    threat_post_id = Column(
        UUID(as_uuid=True),
        ForeignKey("threat_posts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="feed_bookmarks")
    threat_post = relationship("ThreatPost", back_populates="bookmarks")

    __table_args__ = (
        Index("idx_feed_bookmarks_unique", "user_id", "threat_post_id", unique=True),
    )
