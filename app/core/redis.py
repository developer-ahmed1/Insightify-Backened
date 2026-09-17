"""
Redis client for caching, rate limiting, and real-time features.
"""
from contextlib import asynccontextmanager
from typing import Any, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from app.config import settings

# Global redis client state
_redis_client: Optional[Redis] = None
_redis_attempted: bool = False


import asyncio

async def get_redis() -> Optional[Redis]:
    """Get Redis client instance. Returns None if connection fails or Redis is unavailable."""
    global _redis_client, _redis_attempted
    if _redis_attempted:
        return _redis_client

    # In production without an explicit Redis server, skip localhost
    if (
        not settings.redis_url
        or settings.redis_url.strip() in ("", "none", "disabled")
        or (settings.is_production and "localhost" in settings.redis_url)
    ):
        _redis_attempted = True
        return None

    try:
        client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
        )
        await asyncio.wait_for(client.ping(), timeout=1.0)
        _redis_client = client
    except Exception as e:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Redis unavailable: {e}. Operating in cache-free mode.")
        _redis_client = None
    finally:
        _redis_attempted = True

    return _redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client, _redis_attempted
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception:
            pass
        _redis_client = None
    _redis_attempted = False


class RedisCache:
    """Redis cache helper with common operations."""

    def __init__(self, client: Redis):
        self.client = client
        self.prefix = "insightyfy"

    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        return await self.client.get(self._key(key))

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Set value in cache with optional TTL."""
        full_key = self._key(key)
        if ttl:
            await self.client.setex(full_key, ttl, str(value))
        else:
            await self.client.set(full_key, str(value))

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        await self.client.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return bool(await self.client.exists(self._key(key)))

    async def incr(self, key: str) -> int:
        """Increment value and return new value."""
        return await self.client.incr(self._key(key))

    async def expire(self, key: str, ttl: int) -> None:
        """Set TTL on existing key."""
        await self.client.expire(self._key(key), ttl)

    async def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value from cache."""
        import json
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(self, key: str, value: dict, ttl: Optional[int] = None) -> None:
        """Set JSON value in cache."""
        import json
        await self.set(key, json.dumps(value), ttl)


@asynccontextmanager
async def get_cache():
    """Get Redis cache instance."""
    client = await get_redis()
    yield RedisCache(client)
