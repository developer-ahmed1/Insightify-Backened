"""
Education endpoints: scam categories, educational content.
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.detection import ScamCategory
from app.models.education import EducationalContent
from app.schemas.education import (
    ScamCategoryResponse, ScamCategoriesResponse,
    EducationalContentResponse, EducationalContentListResponse,
    ContentHelpfulResponse
)

router = APIRouter()


# Category endpoints
@router.get("/categories", response_model=ScamCategoriesResponse)
async def get_scam_categories(
    db: AsyncSession = Depends(get_db),
):
    """Get all scam categories."""
    result = await db.execute(
        select(ScamCategory)
        .where(ScamCategory.is_active == True)
        .order_by(ScamCategory.name)
    )
    categories = result.scalars().all()
    
    return ScamCategoriesResponse(
        categories=[
            ScamCategoryResponse(
                id=c.id,
                name=c.name,
                slug=c.slug,
                description=c.description,
                icon_url=c.icon_url,
                severity_level=c.severity_level,
            )
            for c in categories
        ]
    )


@router.get("/categories/{category_slug}", response_model=ScamCategoryResponse)
async def get_scam_category(
    category_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific scam category by slug."""
    result = await db.execute(
        select(ScamCategory)
        .where(ScamCategory.slug == category_slug)
        .where(ScamCategory.is_active == True)
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise NotFoundError("Category", category_slug)
    
    return ScamCategoryResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        icon_url=category.icon_url,
        severity_level=category.severity_level,
    )


# Educational content endpoints
@router.get("/content", response_model=EducationalContentListResponse)
async def get_educational_content(
    category_id: Optional[UUID] = None,
    content_type: Optional[str] = None,
    difficulty: Optional[int] = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get educational content with filters."""
    query = (
        select(EducationalContent)
        .options(selectinload(EducationalContent.category))
        .where(EducationalContent.is_published == True)
        .order_by(EducationalContent.created_at.desc())
    )
    
    if category_id:
        query = query.where(EducationalContent.category_id == category_id)
    if content_type:
        query = query.where(EducationalContent.content_type == content_type)
    if difficulty:
        query = query.where(EducationalContent.difficulty_level == difficulty)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    content_list = result.scalars().all()
    
    return EducationalContentListResponse(
        items=[
            EducationalContentResponse(
                id=c.id,
                category_id=c.category_id,
                category_name=c.category.name if c.category else None,
                title=c.title,
                slug=c.slug,
                summary=c.summary,
                content=c.content,
                content_type=c.content_type,
                media_url=c.media_url,
                thumbnail_url=c.thumbnail_url,
                difficulty_level=c.difficulty_level,
                reading_time_minutes=c.reading_time_minutes,
                view_count=c.view_count,
                helpful_count=c.helpful_count,
                tags=c.tags or [],
                created_at=c.created_at,
            )
            for c in content_list
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
    )


@router.get("/content/{content_slug}", response_model=EducationalContentResponse)
async def get_educational_content_detail(
    content_slug: str,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific educational content by slug."""
    result = await db.execute(
        select(EducationalContent)
        .options(selectinload(EducationalContent.category))
        .where(EducationalContent.slug == content_slug)
        .where(EducationalContent.is_published == True)
    )
    content = result.scalar_one_or_none()
    
    if not content:
        raise NotFoundError("Content", content_slug)
    
    # Increment view count
    content.view_count += 1
    await db.flush()
    
    return EducationalContentResponse(
        id=content.id,
        category_id=content.category_id,
        category_name=content.category.name if content.category else None,
        title=content.title,
        slug=content.slug,
        summary=content.summary,
        content=content.content,
        content_type=content.content_type,
        media_url=content.media_url,
        thumbnail_url=content.thumbnail_url,
        difficulty_level=content.difficulty_level,
        reading_time_minutes=content.reading_time_minutes,
        view_count=content.view_count,
        helpful_count=content.helpful_count,
        tags=content.tags or [],
        created_at=content.created_at,
    )


@router.post("/content/{content_slug}/helpful", response_model=ContentHelpfulResponse)
async def mark_content_helpful(
    content_slug: str,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark educational content as helpful."""
    result = await db.execute(
        select(EducationalContent)
        .where(EducationalContent.slug == content_slug)
    )
    content = result.scalar_one_or_none()
    
    if not content:
        raise NotFoundError("Content", content_slug)
    
    # Increment helpful count
    content.helpful_count += 1
    await db.flush()
    
    return ContentHelpfulResponse(
        helpful=True,
        new_count=content.helpful_count,
    )
