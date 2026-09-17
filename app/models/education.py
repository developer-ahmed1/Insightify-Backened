"""
Educational content models.
"""
from uuid import uuid4

from sqlalchemy import (
    Column, ForeignKey, Integer, String, Text, Boolean, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class EducationalContent(Base, TimestampMixin):
    """Educational content about scam types."""

    __tablename__ = "educational_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scam_categories.id"),
        nullable=True,
    )

    title = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=False)  # Markdown content
    
    content_type = Column(String(50), default="article", nullable=False)
    # article, video, infographic, tip
    
    media_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    
    difficulty_level = Column(Integer, default=1, nullable=False)  # 1-5
    reading_time_minutes = Column(Integer, default=5, nullable=False)
    
    # Status
    is_published = Column(Boolean, default=False, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    
    # Stats
    view_count = Column(Integer, default=0, nullable=False)
    helpful_count = Column(Integer, default=0, nullable=False)
    
    # SEO
    meta_description = Column(String(300), nullable=True)
    tags = Column(JSONB, default=list)

    # Relationships
    category = relationship("ScamCategory", back_populates="educational_content")

    __table_args__ = (
        Index("idx_educational_content_slug", "slug"),
        Index("idx_educational_content_category", "category_id"),
        Index("idx_educational_content_published", "is_published"),
    )

    def __repr__(self) -> str:
        return f"<EducationalContent {self.title}>"
