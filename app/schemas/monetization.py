"""
Monetization schemas.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.schemas.common import BaseSchema


class SubscriptionPlanResponse(BaseSchema):
    """Subscription plan response."""
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    
    price_monthly: float
    price_yearly: Optional[float] = None
    currency: str = "USD"
    
    features: Dict[str, Any] = {}
    detection_limit_daily: int
    history_retention_days: int
    
    is_popular: bool = False


class SubscriptionPlansResponse(BaseSchema):
    """List of subscription plans."""
    plans: List[SubscriptionPlanResponse]
    current_plan: Optional[str] = None


class SubscriptionResponse(BaseSchema):
    """User's subscription status."""
    id: UUID
    plan: SubscriptionPlanResponse
    status: str
    billing_cycle: str
    
    current_period_start: datetime
    current_period_end: datetime
    
    is_trial: bool = False
    trial_end: Optional[datetime] = None
    
    cancelled_at: Optional[datetime] = None
    
    created_at: datetime


class SubscriptionStatusResponse(BaseSchema):
    """Quick subscription status check."""
    is_premium: bool
    tier: str
    days_remaining: int
    features: Dict[str, Any] = {}
