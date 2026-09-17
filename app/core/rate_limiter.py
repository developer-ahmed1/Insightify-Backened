"""
Rate limiting based on user subscription tier.
"""
from datetime import date
from typing import Optional, Tuple

from app.config import settings
from app.core.exceptions import RateLimitExceededError
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter with tier-based limits."""

    # Limits by action and tier
    LIMITS = {
        "text_detection": {
            "free": settings.free_text_detections_daily,
            "premium": settings.premium_text_detections_daily,
        },
        "audio_detection": {
            "free": settings.free_audio_detections_daily,
            "premium": settings.premium_audio_detections_daily,
        },
        "video_detection": {
            "free": settings.free_video_detections_daily,
            "premium": settings.premium_video_detections_daily,
        },
        "post": {
            "free": settings.free_posts_daily,
            "premium": settings.premium_posts_daily,
        },
        "comment": {
            "free": 20,
            "premium": 100,
        },
        "report": {
            "free": 10,
            "premium": 50,
        },
    }

    def __init__(self):
        self.prefix = "ratelimit"

    def _get_key(self, user_id: str, action: str) -> str:
        """Generate rate limit key."""
        today = date.today().isoformat()
        return f"{self.prefix}:{action}:{user_id}:{today}"

    def _get_limit(self, action: str, is_premium: bool) -> int:
        """Get limit for action and tier."""
        tier = "premium" if is_premium else "free"
        return self.LIMITS.get(action, {}).get(tier, 0)

    async def check(
        self,
        user_id: str,
        action: str,
        is_premium: bool = False,
    ) -> Tuple[bool, int, int]:
        """
        Check if action is allowed and increment counter.
        
        Args:
            user_id: User ID
            action: Action type (text_detection, audio_detection, etc.)
            is_premium: Whether user has premium subscription
            
        Returns:
            Tuple of (allowed, remaining, limit)
        """
        limit = self._get_limit(action, is_premium)
        
        # If limit is 0, action is not allowed for this tier
        if limit == 0:
            return False, 0, 0

        redis = await get_redis()
        
        # If Redis is unavailable, allow the request (graceful degradation)
        if redis is None:
            logger.warning(f"Redis unavailable, allowing request for {action}")
            return True, limit, limit
        
        key = self._get_key(user_id, action)

        # Increment counter
        current = await redis.incr(key)
        
        # Set expiry on first increment (end of day)
        if current == 1:
            await redis.expire(key, 86400)  # 24 hours

        remaining = max(0, limit - current)
        allowed = current <= limit

        if not allowed:
            logger.warning(
                f"Rate limit exceeded: user={user_id}, action={action}, "
                f"current={current}, limit={limit}"
            )

        return allowed, remaining, limit

    async def check_or_raise(
        self,
        user_id: str,
        action: str,
        is_premium: bool = False,
    ) -> int:
        """
        Check rate limit and raise exception if exceeded.
        
        Returns:
            Remaining count
            
        Raises:
            RateLimitExceededError: If limit exceeded
        """
        allowed, remaining, limit = await self.check(user_id, action, is_premium)
        
        if not allowed:
            raise RateLimitExceededError(
                action=action,
                limit=limit,
                reset_at="midnight UTC",
            )
        
        return remaining

    async def get_remaining(
        self,
        user_id: str,
        action: str,
        is_premium: bool = False,
    ) -> dict:
        """Get remaining limits for an action."""
        limit = self._get_limit(action, is_premium)
        
        if limit == 0:
            return {
                "action": action,
                "limit": 0,
                "used": 0,
                "remaining": 0,
                "allowed": False,
            }

        redis = await get_redis()
        
        # If Redis is unavailable, return defaults
        if redis is None:
            return {
                "action": action,
                "limit": limit,
                "used": 0,
                "remaining": limit,
                "allowed": True,
            }
        
        key = self._get_key(user_id, action)
        
        current = await redis.get(key)
        used = int(current) if current else 0
        remaining = max(0, limit - used)

        return {
            "action": action,
            "limit": limit,
            "used": used,
            "remaining": remaining,
            "allowed": remaining > 0,
        }

    async def get_all_limits(
        self,
        user_id: str,
        is_premium: bool = False,
    ) -> dict:
        """Get all rate limits for a user."""
        limits = {}
        for action in self.LIMITS.keys():
            limits[action] = await self.get_remaining(user_id, action, is_premium)
        return limits


# Singleton instance
rate_limiter = RateLimiter()
