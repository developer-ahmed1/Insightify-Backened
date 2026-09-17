"""
Education schemas.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.schemas.common import BaseSchema


class ScamCategoryResponse(BaseSchema):
    """Scam category response."""
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    severity_level: int


class ScamCategoriesResponse(BaseSchema):
    """List of scam categories."""
    categories: List[ScamCategoryResponse]


class EducationalContentResponse(BaseSchema):
    """Educational content response."""
    id: UUID
    category_id: Optional[UUID] = None
    category_name: Optional[str] = None
    
    title: str
    slug: str
    summary: Optional[str] = None
    content: str
    content_type: str
    
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    
    difficulty_level: int
    reading_time_minutes: int
    view_count: int
    helpful_count: int
    
    tags: List[str] = []
    created_at: datetime


class EducationalContentListResponse(BaseSchema):
    """Paginated educational content."""
    items: List[EducationalContentResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class ContentHelpfulResponse(BaseSchema):
    """Response for marking content as helpful."""
    helpful: bool
    new_count: int
