"""
User service for profile management and XP handling.
"""
import math
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.exceptions import NotFoundError, AlreadyExistsError
from app.models.user import User, UserStreak
from app.schemas.user import UserCreate, UserUpdate

logger = get_logger(__name__)


class UserService:
    """Service for user management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.streak))
            .where(User.id == user_id)
            .where(User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """Get user by Firebase UID."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.streak))
            .where(User.firebase_uid == firebase_uid)
            .where(User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        firebase_uid: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> tuple[User, bool]:
        """
        Get existing user or create new one.
        Returns (user, created) tuple.
        """
        user = await self.get_by_firebase_uid(firebase_uid)
        if user:
            return user, False

        # Create new user
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            display_name=display_name or email.split("@")[0] if email else None,
        )
        self.db.add(user)
        await self.db.flush()

        # Create streak record
        streak = UserStreak(user_id=user.id)
        self.db.add(streak)
        await self.db.flush()

        logger.info(f"Created new user: {user.id} ({email})")
        return user, True

    async def update(self, user_id: UUID, data: UserUpdate) -> User:
        """Update user profile."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        return user

    async def delete(self, user_id: UUID) -> None:
        """Soft delete user."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))
        
        user.soft_delete()
        await self.db.flush()

    # XP and Level methods
    def calculate_level(self, xp: int) -> int:
        """Calculate level from XP (logarithmic growth)."""
        if xp < 100:
            return 1
        return min(100, int(math.log(xp / 100, 1.5)) + 2)

    def xp_for_level(self, level: int) -> int:
        """Calculate XP required for a level."""
        if level <= 1:
            return 100
        return int(100 * (1.5 ** (level - 1)))

    async def add_xp(self, user_id: UUID, xp: int, reason: str = "") -> tuple[int, int, bool]:
        """
        Add XP to user.
        Returns (new_xp, new_level, level_up).
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        old_level = user.level
        user.xp += xp
        user.level = self.calculate_level(user.xp)
        
        level_up = user.level > old_level
        
        if level_up:
            logger.info(f"User {user_id} leveled up to {user.level}")

        await self.db.flush()
        return user.xp, user.level, level_up

    async def update_streak(self, user_id: UUID) -> int:
        """Update user's daily streak. Returns any bonus XP earned."""
        user = await self.get_by_id(user_id)
        if not user or not user.streak:
            return 0

        xp_bonus = user.streak.update_streak()
        
        if xp_bonus > 0:
            await self.add_xp(user_id, xp_bonus, "streak_milestone")
            logger.info(f"User {user_id} earned {xp_bonus} XP for streak milestone")

        await self.db.flush()
        return xp_bonus

    # Stats methods
    async def get_stats(self, user_id: UUID) -> dict:
        """Get user statistics."""
        from app.models.detection import Detection
        from app.models.community import Post
        from app.models.gamification import UserBadge

        # Count detections
        detection_count = await self.db.scalar(
            select(func.count(Detection.id))
            .where(Detection.user_id == user_id)
        )

        # Count posts
        post_count = await self.db.scalar(
            select(func.count(Post.id))
            .where(Post.user_id == user_id)
            .where(Post.deleted_at.is_(None))
        )

        # Count badges
        badge_count = await self.db.scalar(
            select(func.count(UserBadge.id))
            .where(UserBadge.user_id == user_id)
        )

        return {
            "total_detections": detection_count or 0,
            "total_posts": post_count or 0,
            "total_badges": badge_count or 0,
        }

    async def get_leaderboard(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Get XP leaderboard."""
        result = await self.db.execute(
            select(User)
            .where(User.deleted_at.is_(None))
            .where(User.is_active == True)
            .order_by(User.xp.desc())
            .offset(offset)
            .limit(limit)
        )
        users = result.scalars().all()

        return [
            {
                "rank": offset + idx + 1,
                "user_id": user.id,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "xp": user.xp,
                "level": user.level,
            }
            for idx, user in enumerate(users)
        ]
