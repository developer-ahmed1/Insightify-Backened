"""
Admin Panel API — Complete CRUD endpoints for admin dashboard.

All endpoints require admin privileges (is_admin=True).

Sections:
- Dashboard Stats
- User Management
- Threat Feed Management (CRUD)
- Report Management
- Quiz Management (CRUD)
- Badge/Achievement Management (CRUD)
- Daily Tips Management (CRUD)
- Daily Challenges Management (CRUD)
- Notification Broadcasting
- Category & Educational Content Management (CRUD)
"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.models.detection import Detection, ScamCategory
from app.models.community import Post, Report, ModerationLog
from app.models.gamification import Badge, UserBadge, XPRule, Quiz, QuizQuestion, QuizAttempt
from app.models.education import EducationalContent
from app.models.threat_post import ThreatPost
from app.models.notification import Notification
from app.models.daily_tip import DailySafetyTip
from app.models.daily_challenge import DailyChallenge
from app.schemas.common import MessageResponse
from app.schemas.feed import ThreatPostCreateRequest, ThreatPostUpdateRequest

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ===========================================================================
# Dashboard Stats
# ===========================================================================

@router.get("/stats")
async def get_dashboard_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get admin dashboard statistics."""
    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    total_scans = await db.scalar(select(func.count()).select_from(Detection)) or 0
    total_threats = await db.scalar(
        select(func.count()).where(Detection.verdict.in_(["Likely Scam", "Suspicious"]))
    ) or 0
    total_reports = await db.scalar(select(func.count()).select_from(Report)) or 0
    pending_reports = await db.scalar(
        select(func.count()).where(Report.status == "pending")
    ) or 0
    total_quizzes = await db.scalar(select(func.count()).select_from(Quiz)) or 0
    total_feed_posts = await db.scalar(select(func.count()).select_from(ThreatPost)) or 0
    total_badges = await db.scalar(select(func.count()).select_from(Badge)) or 0

    return {
        "totalUsers": total_users,
        "totalScans": total_scans,
        "totalThreatsDetected": total_threats,
        "totalReports": total_reports,
        "pendingReports": pending_reports,
        "totalQuizzes": total_quizzes,
        "totalFeedPosts": total_feed_posts,
        "totalBadges": total_badges,
    }


# ===========================================================================
# User Management
# ===========================================================================

@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users with search and pagination."""
    query = select(User)
    if search:
        query = query.where(
            User.email.ilike(f"%{search}%") |
            User.name.ilike(f"%{search}%") |
            User.username.ilike(f"%{search}%")
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    query = query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name or u.display_name,
                "username": u.username,
                "xp": u.xp,
                "level": u.level,
                "isPremium": u.is_premium,
                "isAdmin": u.is_admin,
                "isActive": u.is_active,
                "createdAt": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.patch("/users/{user_id}/ban")
async def toggle_ban_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Ban or unban a user."""
    uid = UUID(user_id)
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User", user_id)

    user.is_active = not user.is_active
    await db.flush()
    return {"userId": user_id, "isActive": user.is_active}


@router.patch("/users/{user_id}/promote")
async def toggle_admin(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Promote or demote a user to/from admin."""
    uid = UUID(user_id)
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User", user_id)

    user.is_admin = not user.is_admin
    await db.flush()
    return {"userId": user_id, "isAdmin": user.is_admin}


# ===========================================================================
# Threat Feed Management
# ===========================================================================

@router.get("/feed")
async def list_feed_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all threat posts (published + unpublished)."""
    query = select(ThreatPost).order_by(ThreatPost.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(ThreatPost)) or 0
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    posts = result.scalars().all()

    return {
        "posts": [
            {
                "id": str(p.id),
                "title": p.title,
                "riskLevel": p.risk_level,
                "category": p.category,
                "isPublished": p.is_published,
                "isVerified": p.is_verified,
                "isFeatured": p.is_featured,
                "reportCount": p.report_count,
                "viewCount": p.view_count,
                "createdAt": p.created_at.isoformat() if p.created_at else None,
            }
            for p in posts
        ],
        "total": total,
        "page": page,
    }


@router.post("/feed", status_code=201)
async def create_feed_post(
    request: ThreatPostCreateRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new threat feed post."""
    post = ThreatPost(
        risk_level=request.riskLevel,
        title=request.title,
        description=request.description,
        category=request.category,
        platform_tag=request.platformTag,
        location=request.location,
        is_verified=request.isVerified,
        is_published=request.isPublished,
        media=request.media,
        reported_by=request.reportedBy,
        what_is_happening=request.whatIsHappening,
        example_content=request.exampleContent,
        safety_tips=request.safetyTips,
        created_by_id=admin.id,
    )
    db.add(post)
    await db.flush()
    return {"id": str(post.id), "message": "Threat post created"}


@router.put("/feed/{post_id}")
async def update_feed_post(
    post_id: str,
    request: ThreatPostUpdateRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a threat feed post."""
    uid = UUID(post_id)
    result = await db.execute(select(ThreatPost).where(ThreatPost.id == uid))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundError("ThreatPost", post_id)

    update_data = request.model_dump(exclude_none=True)
    field_map = {
        "riskLevel": "risk_level", "platformTag": "platform_tag",
        "isVerified": "is_verified", "isPublished": "is_published",
        "reportedBy": "reported_by", "whatIsHappening": "what_is_happening",
        "exampleContent": "example_content", "safetyTips": "safety_tips",
    }
    for key, value in update_data.items():
        db_field = field_map.get(key, key)
        setattr(post, db_field, value)

    await db.flush()
    return {"id": post_id, "message": "Updated"}


@router.delete("/feed/{post_id}")
async def delete_feed_post(
    post_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a threat feed post."""
    uid = UUID(post_id)
    result = await db.execute(select(ThreatPost).where(ThreatPost.id == uid))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundError("ThreatPost", post_id)

    await db.delete(post)
    await db.flush()
    return {"message": "Deleted"}


# ===========================================================================
# Report Management
# ===========================================================================

@router.get("/reports")
async def list_reports(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all reports with optional status filter."""
    query = select(Report)
    if status:
        query = query.where(Report.status == status)

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    query = query.order_by(Report.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    reports = result.scalars().all()

    return {
        "reports": [
            {
                "id": str(r.id),
                "reporterId": str(r.reporter_id) if r.reporter_id else None,
                "reason": r.reason,
                "description": r.description,
                "status": r.status,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
                "resolvedAt": r.resolved_at.isoformat() if r.resolved_at else None,
            }
            for r in reports
        ],
        "total": total,
        "page": page,
    }


@router.patch("/reports/{report_id}")
async def resolve_report(
    report_id: str,
    action: str = Query(..., description="approve | dismiss | action_taken"),
    notes: Optional[str] = Query(None),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a report."""
    uid = UUID(report_id)
    result = await db.execute(select(Report).where(Report.id == uid))
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report", report_id)

    status_map = {"approve": "reviewed", "dismiss": "dismissed", "action_taken": "action_taken"}
    report.status = status_map.get(action, "reviewed")
    report.resolution_notes = notes
    report.resolved_at = datetime.now(timezone.utc)
    report.resolved_by_id = admin.id
    await db.flush()
    return {"id": report_id, "status": report.status}


# ===========================================================================
# Quiz Management
# ===========================================================================

@router.get("/quizzes")
async def list_quizzes(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all quizzes."""
    result = await db.execute(select(Quiz).order_by(Quiz.created_at.desc()))
    quizzes = result.scalars().all()
    return {
        "quizzes": [
            {
                "id": str(q.id),
                "title": q.title,
                "difficultyLevel": q.difficulty_level,
                "xpReward": q.xp_reward,
                "isActive": q.is_active,
                "isFeatured": q.is_featured,
                "totalAttempts": q.total_attempts,
            }
            for q in quizzes
        ]
    }


@router.post("/quizzes", status_code=201)
async def create_quiz(
    title: str = Query(...),
    description: Optional[str] = Query(None),
    difficulty_level: int = Query(1),
    xp_reward: int = Query(50),
    category_id: Optional[str] = Query(None),
    time_limit_seconds: Optional[int] = Query(None),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new quiz."""
    quiz = Quiz(
        title=title,
        description=description,
        difficulty_level=difficulty_level,
        xp_reward=xp_reward,
        category_id=UUID(category_id) if category_id else None,
        time_limit_seconds=time_limit_seconds,
        is_active=True,
    )
    db.add(quiz)
    await db.flush()
    return {"id": str(quiz.id), "message": "Quiz created"}


@router.post("/quizzes/{quiz_id}/questions", status_code=201)
async def add_quiz_question(
    quiz_id: str,
    question: str = Query(...),
    question_type: str = Query("mcq"),
    options: str = Query(..., description="Comma-separated options"),
    correct_answer: str = Query(...),
    explanation: Optional[str] = Query(None),
    points: int = Query(10),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a question to a quiz."""
    uid = UUID(quiz_id)

    # Get max order index
    max_order = await db.scalar(
        select(func.max(QuizQuestion.order_index)).where(QuizQuestion.quiz_id == uid)
    ) or 0

    q = QuizQuestion(
        quiz_id=uid,
        question_type=question_type,
        question=question,
        options=[opt.strip() for opt in options.split(",")],
        correct_answer=correct_answer,
        explanation=explanation,
        order_index=max_order + 1,
        points=points,
    )
    db.add(q)
    await db.flush()
    return {"id": str(q.id), "message": "Question added"}


@router.delete("/quizzes/{quiz_id}")
async def delete_quiz(
    quiz_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a quiz."""
    uid = UUID(quiz_id)
    result = await db.execute(select(Quiz).where(Quiz.id == uid))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise NotFoundError("Quiz", quiz_id)
    await db.delete(quiz)
    await db.flush()
    return {"message": "Deleted"}


# ===========================================================================
# Badge Management
# ===========================================================================

@router.get("/badges")
async def list_badges(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all badges."""
    result = await db.execute(select(Badge).order_by(Badge.category))
    badges = result.scalars().all()
    return {
        "badges": [
            {
                "id": str(b.id),
                "name": b.name,
                "slug": b.slug,
                "category": b.category,
                "xpReward": b.xp_reward,
                "isActive": b.is_active,
            }
            for b in badges
        ]
    }


@router.post("/badges", status_code=201)
async def create_badge(
    name: str = Query(...),
    slug: str = Query(...),
    description: Optional[str] = Query(None),
    category: str = Query("detection"),
    xp_reward: int = Query(0),
    icon_url: Optional[str] = Query(None),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new badge."""
    badge = Badge(
        name=name, slug=slug, description=description,
        category=category, xp_reward=xp_reward, icon_url=icon_url,
    )
    db.add(badge)
    await db.flush()
    return {"id": str(badge.id), "message": "Badge created"}


# ===========================================================================
# Daily Tips Management
# ===========================================================================

@router.get("/tips")
async def list_tips(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all daily safety tips."""
    result = await db.execute(select(DailySafetyTip).order_by(DailySafetyTip.created_at.desc()))
    tips = result.scalars().all()
    return {
        "tips": [
            {
                "id": str(t.id),
                "title": t.title,
                "content": t.content,
                "category": t.category,
                "activeDate": t.active_date.isoformat() if t.active_date else None,
                "isActive": t.is_active,
            }
            for t in tips
        ]
    }


@router.post("/tips", status_code=201)
async def create_tip(
    title: str = Query(...),
    content: str = Query(...),
    category: str = Query("credential_safety"),
    active_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new daily safety tip."""
    tip = DailySafetyTip(
        title=title,
        content=content,
        category=category,
        active_date=date.fromisoformat(active_date) if active_date else None,
    )
    db.add(tip)
    await db.flush()
    return {"id": str(tip.id), "message": "Tip created"}


@router.delete("/tips/{tip_id}")
async def delete_tip(
    tip_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a daily tip."""
    uid = UUID(tip_id)
    result = await db.execute(select(DailySafetyTip).where(DailySafetyTip.id == uid))
    tip = result.scalar_one_or_none()
    if not tip:
        raise NotFoundError("DailySafetyTip", tip_id)
    await db.delete(tip)
    await db.flush()
    return {"message": "Deleted"}


# ===========================================================================
# Daily Challenges Management
# ===========================================================================

@router.get("/challenges")
async def list_challenges(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all daily challenges."""
    result = await db.execute(select(DailyChallenge).order_by(DailyChallenge.active_date.desc()))
    challenges = result.scalars().all()
    return {
        "challenges": [
            {
                "id": str(c.id),
                "title": c.title,
                "subtitle": c.subtitle,
                "rewardXp": c.reward_xp,
                "quizId": str(c.quiz_id) if c.quiz_id else None,
                "activeDate": c.active_date.isoformat() if c.active_date else None,
                "isActive": c.is_active,
            }
            for c in challenges
        ]
    }


@router.post("/challenges", status_code=201)
async def create_challenge(
    title: str = Query(...),
    subtitle: Optional[str] = Query(None),
    reward_xp: int = Query(50),
    quiz_id: Optional[str] = Query(None),
    active_date: str = Query(..., description="YYYY-MM-DD"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new daily challenge."""
    challenge = DailyChallenge(
        title=title,
        subtitle=subtitle,
        reward_xp=reward_xp,
        quiz_id=UUID(quiz_id) if quiz_id else None,
        active_date=date.fromisoformat(active_date),
    )
    db.add(challenge)
    await db.flush()
    return {"id": str(challenge.id), "message": "Challenge created"}


# ===========================================================================
# Categories Management
# ===========================================================================

@router.get("/categories")
async def list_categories(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all scam categories."""
    result = await db.execute(select(ScamCategory).order_by(ScamCategory.name))
    categories = result.scalars().all()
    return {
        "categories": [
            {
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug,
                "description": c.description,
                "severityLevel": c.severity_level,
                "isActive": c.is_active,
            }
            for c in categories
        ]
    }


@router.post("/categories", status_code=201)
async def create_category(
    name: str = Query(...),
    slug: str = Query(...),
    description: Optional[str] = Query(None),
    severity_level: int = Query(5),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a scam category."""
    cat = ScamCategory(
        name=name, slug=slug, description=description,
        severity_level=severity_level,
    )
    db.add(cat)
    await db.flush()
    return {"id": str(cat.id), "message": "Category created"}


# ===========================================================================
# Notifications Broadcasting
# ===========================================================================

@router.post("/notifications/broadcast", status_code=201)
async def broadcast_notification(
    title: str = Query(...),
    message: Optional[str] = Query(None),
    type: str = Query("system"),
    user_id: Optional[str] = Query(None, description="Target user or None for all"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a notification to a specific user or broadcast to all."""
    if user_id:
        # Single user notification
        notif = Notification(
            user_id=UUID(user_id),
            type=type,
            title=title,
            message=message,
        )
        db.add(notif)
        await db.flush()
        return {"message": "Notification sent", "count": 1}
    else:
        # Broadcast to all active users
        result = await db.execute(select(User.id).where(User.is_active == True))
        user_ids = [row[0] for row in result.all()]

        for uid in user_ids:
            notif = Notification(
                user_id=uid,
                type=type,
                title=title,
                message=message,
            )
            db.add(notif)

        await db.flush()
        return {"message": "Broadcast sent", "count": len(user_ids)}


# ===========================================================================
# XP Rules Management
# ===========================================================================

@router.get("/xp-rules")
async def list_xp_rules(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all XP rules."""
    result = await db.execute(select(XPRule).order_by(XPRule.action))
    rules = result.scalars().all()
    return {
        "rules": [
            {
                "id": str(r.id),
                "action": r.action,
                "baseXp": r.base_xp,
                "dailyLimit": r.daily_limit,
                "isActive": r.is_active,
            }
            for r in rules
        ]
    }


@router.post("/xp-rules", status_code=201)
async def create_xp_rule(
    action: str = Query(...),
    base_xp: int = Query(...),
    description: Optional[str] = Query(None),
    daily_limit: Optional[int] = Query(None),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an XP rule."""
    rule = XPRule(
        action=action, base_xp=base_xp,
        description=description, daily_limit=daily_limit,
    )
    db.add(rule)
    await db.flush()
    return {"id": str(rule.id), "message": "XP rule created"}
