"""
Community feed endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_active_user, get_feed_service
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.community import (
    PostCreate, PostUpdate, PostResponse, PostListResponse, FeedType,
    CommentCreate, CommentResponse, ReactionCreate, ReactionResponse,
    ReportCreate, ReportResponse, AuthorResponse
)
from app.schemas.common import MessageResponse
from app.services.feed_service import FeedService

router = APIRouter()


# Feed endpoints
@router.get("", response_model=PostListResponse)
async def get_feed(
    feed_type: FeedType = Query(FeedType.LATEST, description="Feed sorting type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Get community feed with sorting options."""
    posts, total = await service.get_feed(
        feed_type=feed_type,
        page=page,
        page_size=page_size,
        user_id=user.id,
    )
    
    # Get user reactions for each post
    items = []
    for post in posts:
        reaction = await service.get_user_reaction(user.id, post_id=post.id)
        items.append(service.post_to_response(post, user_reaction=reaction))
    
    return PostListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
        feed_type=feed_type,
    )


# Post endpoints
@router.post("/posts", response_model=PostResponse)
async def create_post(
    data: PostCreate,
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Create a new post."""
    post = await service.create_post(user, data)
    return service.post_to_response(post)


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Get a specific post."""
    post = await service.get_post_by_id(post_id)
    if not post:
        raise NotFoundError("Post", str(post_id))
    
    reaction = await service.get_user_reaction(user.id, post_id=post.id)
    return service.post_to_response(post, user_reaction=reaction)


@router.patch("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: UUID,
    data: PostUpdate,
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Update a post (owner only)."""
    post = await service.update_post(post_id, user.id, data)
    return service.post_to_response(post)


@router.delete("/posts/{post_id}", response_model=MessageResponse)
async def delete_post(
    post_id: UUID,
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Delete a post (owner only)."""
    await service.delete_post(post_id, user.id)
    return MessageResponse(message="Post deleted successfully")


# Reaction endpoints
@router.post("/posts/{post_id}/reactions", response_model=ReactionResponse)
async def toggle_post_reaction(
    post_id: UUID,
    data: ReactionCreate,
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Toggle reaction on a post."""
    is_added, new_count = await service.toggle_reaction(
        user.id, 
        post_id=post_id, 
        reaction_type=data.reaction_type.value
    )
    return ReactionResponse(
        success=True,
        reaction_type=data.reaction_type if is_added else None,
        new_count=new_count,
    )


# Comment endpoints
@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
async def get_post_comments(
    post_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Get comments for a post."""
    comments, _ = await service.get_comments(post_id, page, page_size)
    
    return [
        CommentResponse(
            id=c.id,
            post_id=c.post_id,
            author=AuthorResponse(
                id=c.user.id,
                display_name=c.user.display_name,
                avatar_url=c.user.avatar_url,
                level=c.user.level,
                is_premium=c.user.is_premium,
            ),
            content=c.content,
            like_count=c.like_count,
            parent_id=c.parent_id,
            replies_count=len(c.replies) if hasattr(c, 'replies') else 0,
            created_at=c.created_at,
        )
        for c in comments
    ]


@router.post("/posts/{post_id}/comments", response_model=CommentResponse)
async def create_comment(
    post_id: UUID,
    data: CommentCreate,
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Create a comment on a post."""
    comment = await service.create_comment(post_id, user, data)
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author=AuthorResponse(
            id=user.id,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            level=user.level,
            is_premium=user.is_premium,
        ),
        content=comment.content,
        like_count=0,
        parent_id=comment.parent_id,
        replies_count=0,
        created_at=comment.created_at,
    )


# Report endpoints
@router.post("/posts/{post_id}/report", response_model=ReportResponse)
async def report_post(
    post_id: UUID,
    data: ReportCreate,
    user: User = Depends(get_current_active_user),
    service: FeedService = Depends(get_feed_service),
):
    """Report a post for moderation."""
    report = await service.create_report(user.id, data, post_id=post_id)
    return ReportResponse(id=report.id)
