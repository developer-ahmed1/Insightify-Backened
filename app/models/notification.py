"""
Notification model.
RFC §15 — Notifications APIs.
"""
from uuid import uuid4

from sqlalchemy import (
    Column, ForeignKey, Integer, String, Text, Boolean, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    """
    User notification record.

    RFC §15.2 — Unread count badge on Home.
    Future: Full notification list, mark-as-read, push history.
    """

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Notification content
    type = Column(String(50), nullable=False)
    # scam_alert | achievement | leaderboard | report_update | system
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)

    # Optional structured data payload
    data = Column(JSONB, nullable=True)
    # e.g. {"threatId": "threat_001"} or {"achievementId": "a1"}

    # Relationships
    user = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("idx_notifications_user_unread", "user_id", "is_read"),
        Index("idx_notifications_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.type} for user={self.user_id}>"
