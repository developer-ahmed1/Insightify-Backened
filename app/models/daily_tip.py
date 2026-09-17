"""
Daily safety tip model.
RFC §5.4 — Daily Safety Tip for Home dashboard.
"""
from uuid import uuid4

from sqlalchemy import Column, String, Text, Boolean, Date, Index
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class DailySafetyTip(Base, TimestampMixin):
    """
    Daily cybersecurity micro-learning tip.

    RFC §5.4 response:
    {
        "id": "tip_001",
        "title": "Daily Safety Tip",
        "content": "Never share OTPs...",
        "category": "credential_safety"
    }
    """

    __tablename__ = "daily_safety_tips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    # credential_safety | phishing | social_engineering | privacy | malware

    # Scheduling
    active_date = Column(Date, nullable=True, index=True)
    # If set, this tip is shown on this specific date
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_daily_tips_active_date", "active_date"),
    )

    def __repr__(self) -> str:
        return f"<DailySafetyTip {self.title[:40]}>"
