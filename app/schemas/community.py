"""
Community feed schemas.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class PostType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class ReactionType(str, Enum):
    LIKE = "like"
    HELPFUL = "helpful"
    WARNING = "warning"


class ReportReason(str, Enum):
    MISINFORMATION = "misinformation"
    SPAM = "spam"
    HARASSMENT = "harassment"
    INAPPROPRIATE = "inappropriate"
    OTHER = "other"


class FeedType(str, Enum):
    LATEST = "latest"
    TRENDING = "trending"
    EDUCATIONAL = "educational"


# Post schemas
class PostCreate(BaseSchema):
    """Schema for creating a post."""
    post_type: PostType = PostType.TEXT
    title: Optional[str] = Field(None, max_length=200)
    content: str = Field(..., min_length=10, max_length=5000)
    media_url: Optional[str] = None
    tags: List[str] = []
    scam_category_id: Optional[UUID] = None


class PostUpdate(BaseSchema):
    """Schema for updating a post."""
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, min_length=10, max_length=5000)
    tags: Optional[List[str]] = None


class AuthorResponse(BaseSchema):
    """Post/comment author info."""
    id: UUID
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    level: int = 1
    is_premium: bool = False


class PostResponse(BaseSchema):
    """Post response schema."""
    id: UUID
    author: AuthorResponse
    post_type: PostType
    title: Optional[str] = None
    content: str
    media_url: Optional[str] = None
    media_thumbnail_url: Optional[str] = None
    
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    
    is_featured: bool = False
    is_pinned: bool = False
    tags: List[str] = []
    
    # Current user's state
    user_reaction: Optional[str] = None
    user_reported: bool = False
    
    created_at: datetime
    updated_at: datetime


class PostListResponse(BaseSchema):
    """Paginated post list."""
    items: List[PostResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    feed_type: FeedType


# Comment schemas
class CommentCreate(BaseSchema):
    """Schema for creating a comment."""
    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: Optional[UUID] = None


class CommentResponse(BaseSchema):
    """Comment response schema."""
    id: UUID
    post_id: UUID
    author: AuthorResponse
    content: str
    like_count: int = 0
    parent_id: Optional[UUID] = None
    replies_count: int = 0
    user_reaction: Optional[str] = None
    created_at: datetime


# Reaction schemas
class ReactionCreate(BaseSchema):
    """Schema for creating a reaction."""
    reaction_type: ReactionType = ReactionType.LIKE


class ReactionResponse(BaseSchema):
    """Reaction response."""
    success: bool
    reaction_type: Optional[ReactionType] = None
    new_count: int


# Report schemas
class ReportCreate(BaseSchema):
    """Schema for reporting content."""
    reason: ReportReason
    description: Optional[str] = Field(None, max_length=1000)


class ReportResponse(BaseSchema):
    """Report submitted response."""
    id: UUID
    message: str = "Report submitted successfully"
