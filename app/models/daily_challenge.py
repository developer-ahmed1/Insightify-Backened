"""
Daily challenge model.
RFC §11.3 — Daily Challenge for Quiz dashboard.
"""
from uuid import uuid4

from sqlalchemy import Column, ForeignKey, Integer, String, Text, Boolean, Date, Index
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class DailyChallenge(Base, TimestampMixin):
    """
    Daily featured micro-challenge linking to a quiz.

    RFC §11.3 response:
    {
        "id": "daily_challenge_01",
        "quizId": "phishing-basics",
        "title": "Spot the Real Link",
        "subtitle": "Can you identify the real website?",
        "rewardXp": 50,
        "timeRemainingSeconds": 27932
    }
    """

    __tablename__ = "daily_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    quiz_id = Column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="SET NULL"),
        nullable=True,
    )

    title = Column(String(200), nullable=False)
    subtitle = Column(Text, nullable=True)
    reward_xp = Column(Integer, default=50, nullable=False)

    # Scheduling
    active_date = Column(Date, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_daily_challenges_date", "active_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyChallenge {self.title[:40]} date={self.active_date}>"
