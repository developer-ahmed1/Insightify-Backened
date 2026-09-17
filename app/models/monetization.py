"""
Monetization models: subscription plans and user subscriptions.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, Text, 
    Boolean, Numeric, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class SubscriptionPlan(Base, TimestampMixin):
    """Subscription plan configuration."""

    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(50), unique=True, nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Pricing
    price_monthly = Column(Numeric(10, 2), nullable=False)
    price_yearly = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Features (for display and gating)
    features = Column(JSONB, default=dict)
    # {
    #   "text_detections_daily": 100,
    #   "audio_detections_daily": 50,
    #   "video_detections_daily": 20,
    #   "history_retention_days": 90,
    #   "show_ads": false,
    #   "xp_multiplier": 1.5
    # }
    
    # Limits (used by rate limiter)
    detection_limit_daily = Column(Integer, default=100, nullable=False)
    history_retention_days = Column(Integer, default=90, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_popular = Column(Boolean, default=False, nullable=False)  # Highlight badge
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")

    __table_args__ = (
        Index("idx_subscription_plans_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan {self.name}>"


class Subscription(Base, TimestampMixin):
    """User's active subscription."""

    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id"),
        nullable=False,
    )

    # Status
    status = Column(String(20), default="active", nullable=False)
    # active, cancelled, past_due, expired
    
    # Billing
    payment_provider = Column(String(50), nullable=True)
    # stripe, google_play, apple_iap
    external_subscription_id = Column(String(200), nullable=True)
    billing_cycle = Column(String(20), default="monthly", nullable=False)
    # monthly, yearly
    
    # Period
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    
    # Cancellation
    cancelled_at = Column(DateTime, nullable=True)
    cancel_reason = Column(Text, nullable=True)
    
    # Trial
    trial_end = Column(DateTime, nullable=True)
    is_trial = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscription")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")

    __table_args__ = (
        Index("idx_subscriptions_user", "user_id"),
        Index("idx_subscriptions_status", "status"),
        Index("idx_subscriptions_period_end", "current_period_end"),
    )

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        if self.status != "active":
            return False
        return datetime.utcnow() < self.current_period_end

    @property
    def is_cancelled(self) -> bool:
        """Check if subscription is cancelled."""
        return self.cancelled_at is not None

    def __repr__(self) -> str:
        return f"<Subscription user={self.user_id} plan={self.plan_id}>"
