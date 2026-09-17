"""
Scan bookmark model for detection history bookmarks.
RFC §10.3 — Toggle Scan Result Bookmark.
"""
from uuid import uuid4

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class ScanBookmark(Base, TimestampMixin):
    """User bookmark on a scan result. RFC §10.3."""

    __tablename__ = "scan_bookmarks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    detection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("detections.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="scan_bookmarks")
    detection = relationship("Detection", back_populates="bookmarks")

    __table_args__ = (
        Index("idx_scan_bookmarks_unique", "user_id", "detection_id", unique=True),
    )
