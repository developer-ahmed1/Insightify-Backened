"""
Community feed service.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.rate_limiter import rate_limiter
from app.core.exceptions import NotFoundError, ForbiddenError
from app.models.user import User
from app.models.community import Post, Comment, Reaction, Report
from app.schemas.community import (
    PostCreate, PostUpdate, PostResponse, FeedType,
    CommentCreate, CommentResponse, ReactionCreate, ReportCreate,
    AuthorResponse
)

logger = get_logger(__name__)


class FeedService:
    """Service for community feed operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Post methods
    async def create_post(self, user: User, data: PostCreate) -> Post:
        """Create a new post."""
        # Check rate limit
        await rate_limiter.check_or_raise(
            str(user.id),
            "post",
            user.is_premium,
        )

        post = Post(
            user_id=user.id,
            post_type=data.post_type.value,
            title=data.title,
            content=data.content,
            media_url=data.media_url,
            tags=data.tags,
            scam_category_id=data.scam_category_id,
            moderation_status="approved",  # Auto-approve for MVP
        )

        self.db.add(post)
        await self.db.flush()

        logger.info(f"Post created: {post.id} by user {user.id}")
        return post

    async def update_post(
        self, 
        post_id: UUID, 
        user_id: UUID, 
        data: PostUpdate
    ) -> Post:
        """Update a post (owner only)."""
        post = await self.get_post_by_id(post_id)
        if not post:
            raise NotFoundError("Post", str(post_id))
        
        if post.user_id != user_id:
            raise ForbiddenError("You can only edit your own posts")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(post, field, value)

        await self.db.flush()
        return post

    async def delete_post(self, post_id: UUID, user_id: UUID) -> None:
        """Soft delete a post (owner only)."""
        post = await self.get_post_by_id(post_id)
        if not post:
            raise NotFoundError("Post", str(post_id))
        
        if post.user_id != user_id:
            raise ForbiddenError("You can only delete your own posts")

        post.soft_delete()
        await self.db.flush()

    async def get_post_by_id(self, post_id: UUID) -> Optional[Post]:
        """Get post by ID."""
        result = await self.db.execute(
            select(Post)
            .options(selectinload(Post.user))
            .where(Post.id == post_id)
            .where(Post.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    # Feed methods
    async def get_feed(
        self,
        feed_type: FeedType,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[UUID] = None,
    ) -> tuple[List[Post], int]:
        """Get paginated feed."""
        base_query = (
            select(Post)
            .options(selectinload(Post.user))
            .where(Post.deleted_at.is_(None))
            .where(Post.moderation_status == "approved")
        )

        # Apply sorting based on feed type
        if feed_type == FeedType.LATEST:
            query = base_query.order_by(Post.created_at.desc())
        elif feed_type == FeedType.TRENDING:
            # Simple trending: most likes in recent posts
            query = base_query.order_by(
                Post.like_count.desc(),
                Post.created_at.desc()
            )
        elif feed_type == FeedType.EDUCATIONAL:
            query = base_query.order_by(
                Post.educational_score.desc(),
                Post.created_at.desc()
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        posts = result.scalars().all()

        return posts, total

    async def get_user_posts(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Post], int]:
        """Get posts by a specific user."""
        query = (
            select(Post)
            .options(selectinload(Post.user))
            .where(Post.user_id == user_id)
            .where(Post.deleted_at.is_(None))
            .order_by(Post.created_at.desc())
        )

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        posts = result.scalars().all()

        return posts, total

    # Comment methods
    async def create_comment(
        self,
        post_id: UUID,
        user: User,
        data: CommentCreate,
    ) -> Comment:
        """Create a comment on a post."""
        post = await self.get_post_by_id(post_id)
        if not post:
            raise NotFoundError("Post", str(post_id))

        await rate_limiter.check_or_raise(
            str(user.id),
            "comment",
            user.is_premium,
        )

        comment = Comment(
            post_id=post_id,
            user_id=user.id,
            content=data.content,
            parent_id=data.parent_id,
        )

        self.db.add(comment)

        # Update post comment count
        post.comment_count += 1

        await self.db.flush()
        return comment

    async def get_comments(
        self,
        post_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Comment], int]:
        """Get comments for a post."""
        query = (
            select(Comment)
            .options(selectinload(Comment.user))
            .where(Comment.post_id == post_id)
            .where(Comment.deleted_at.is_(None))
            .where(Comment.parent_id.is_(None))  # Top-level only
            .order_by(Comment.created_at.asc())
        )

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        comments = result.scalars().all()

        return comments, total

    # Reaction methods
    async def toggle_reaction(
        self,
        user_id: UUID,
        post_id: Optional[UUID] = None,
        comment_id: Optional[UUID] = None,
        reaction_type: str = "like",
    ) -> tuple[bool, int]:
        """Toggle reaction on post or comment. Returns (is_added, new_count)."""
        # Check if reaction exists
        query = select(Reaction).where(Reaction.user_id == user_id)
        
        if post_id:
            query = query.where(Reaction.post_id == post_id)
            target = await self.get_post_by_id(post_id)
            if not target:
                raise NotFoundError("Post", str(post_id))
        elif comment_id:
            query = query.where(Reaction.comment_id == comment_id)
            # Fetch comment for count update
            result = await self.db.execute(
                select(Comment).where(Comment.id == comment_id)
            )
            target = result.scalar_one_or_none()
            if not target:
                raise NotFoundError("Comment", str(comment_id))

        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            # Remove reaction
            await self.db.delete(existing)
            target.like_count = max(0, target.like_count - 1)
            await self.db.flush()
            return False, target.like_count
        else:
            # Add reaction
            reaction = Reaction(
                user_id=user_id,
                post_id=post_id,
                comment_id=comment_id,
                reaction_type=reaction_type,
            )
            self.db.add(reaction)
            target.like_count += 1
            await self.db.flush()
            return True, target.like_count

    async def get_user_reaction(
        self,
        user_id: UUID,
        post_id: Optional[UUID] = None,
        comment_id: Optional[UUID] = None,
    ) -> Optional[str]:
        """Get user's reaction to a post or comment."""
        query = select(Reaction).where(Reaction.user_id == user_id)
        
        if post_id:
            query = query.where(Reaction.post_id == post_id)
        elif comment_id:
            query = query.where(Reaction.comment_id == comment_id)
        else:
            return None

        result = await self.db.execute(query)
        reaction = result.scalar_one_or_none()
        return reaction.reaction_type if reaction else None

    # Report methods
    async def create_report(
        self,
        reporter_id: UUID,
        data: ReportCreate,
        post_id: Optional[UUID] = None,
        comment_id: Optional[UUID] = None,
    ) -> Report:
        """Create a content report."""
        await rate_limiter.check_or_raise(
            str(reporter_id),
            "report",
            False,  # Reports always use free tier limits
        )

        report = Report(
            reporter_id=reporter_id,
            post_id=post_id,
            comment_id=comment_id,
            reason=data.reason.value,
            description=data.description,
        )

        self.db.add(report)

        # Increment report count
        if post_id:
            post = await self.get_post_by_id(post_id)
            if post:
                post.report_count += 1

        await self.db.flush()
        
        logger.info(f"Report created: {report.id} for post={post_id} comment={comment_id}")
        return report

    # Helper methods
    def post_to_response(
        self,
        post: Post,
        user_reaction: Optional[str] = None,
        user_reported: bool = False,
    ) -> PostResponse:
        """Convert post model to response schema."""
        return PostResponse(
            id=post.id,
            author=AuthorResponse(
                id=post.user.id,
                display_name=post.user.display_name,
                avatar_url=post.user.avatar_url,
                level=post.user.level,
                is_premium=post.user.is_premium,
            ),
            post_type=post.post_type,
            title=post.title,
            content=post.content,
            media_url=post.media_url,
            media_thumbnail_url=post.media_thumbnail_url,
            like_count=post.like_count,
            comment_count=post.comment_count,
            share_count=post.share_count,
            is_featured=post.is_featured,
            is_pinned=post.is_pinned,
            tags=post.tags or [],
            user_reaction=user_reaction,
            user_reported=user_reported,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )
