"""
Community feed models: posts, comments, reactions, reports.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, Text, 
    Boolean, Float, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class Post(Base, TimestampMixin, SoftDeleteMixin):
    """Community post model."""

    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Content
    post_type = Column(String(20), default="text", nullable=False)  # text, image, video
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=False)
    media_url = Column(String(500), nullable=True)
    media_thumbnail_url = Column(String(500), nullable=True)

    # Engagement metrics (denormalized for performance)
    like_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    share_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    report_count = Column(Integer, default=0, nullable=False)

    # AI scoring
    educational_score = Column(Float, default=0.0, nullable=False)  # 0-100
    moderation_score = Column(Float, nullable=True)  # AI moderation confidence

    # Status
    is_featured = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    moderation_status = Column(String(20), default="pending", nullable=False)
    # pending, approved, flagged, removed

    # Metadata
    tags = Column(JSONB, default=list)
    scam_category_id = Column(UUID(as_uuid=True), ForeignKey("scam_categories.id"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="post", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="post")
    moderation_logs = relationship("ModerationLog", back_populates="post")

    __table_args__ = (
        Index("idx_posts_trending", "like_count", "created_at"),
        Index("idx_posts_educational", "educational_score"),
        Index("idx_posts_user", "user_id"),
        Index("idx_posts_moderation", "moderation_status"),
    )

    def __repr__(self) -> str:
        return f"<Post {self.id} by user={self.user_id}>"


class Comment(Base, TimestampMixin, SoftDeleteMixin):
    """Comment on a post."""

    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id = Column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    content = Column(Text, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    moderation_status = Column(String(20), default="approved", nullable=False)

    # Relationships
    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], backref="replies")
    reactions = relationship("Reaction", back_populates="comment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_comments_post", "post_id"),
    )

    def __repr__(self) -> str:
        return f"<Comment {self.id} on post={self.post_id}>"


class Reaction(Base, TimestampMixin):
    """Reaction (like/emoji) on post or comment."""

    __tablename__ = "reactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    post_id = Column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=True,
    )
    comment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    reaction_type = Column(String(20), default="like", nullable=False)
    # like, helpful, warning, etc.

    # Relationships
    user = relationship("User")
    post = relationship("Post", back_populates="reactions")
    comment = relationship("Comment", back_populates="reactions")

    __table_args__ = (
        Index("idx_reactions_user_post", "user_id", "post_id"),
        Index("idx_reactions_user_comment", "user_id", "comment_id"),
    )


class Report(Base, TimestampMixin):
    """Report for content moderation."""

    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    reporter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    post_id = Column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=True,
    )
    comment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    reason = Column(String(100), nullable=False)
    # misinformation, spam, harassment, inappropriate, other
    description = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    # pending, reviewed, dismissed, action_taken
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id])
    post = relationship("Post", back_populates="reports")
    comment = relationship("Comment")

    __table_args__ = (
        Index("idx_reports_status", "status"),
        Index("idx_reports_post", "post_id"),
    )


class ModerationLog(Base, TimestampMixin):
    """Audit log for moderation actions."""

    __tablename__ = "moderation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=True)
    comment_id = Column(UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True)

    action = Column(String(50), nullable=False)
    # approve, flag, remove, restore, feature
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=True)
    
    confidence_score = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    
    moderator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_automated = Column(Boolean, default=False, nullable=False)

    # Relationships
    post = relationship("Post", back_populates="moderation_logs")
    moderator = relationship("User")

    __table_args__ = (
        Index("idx_moderation_logs_post", "post_id"),
    )
