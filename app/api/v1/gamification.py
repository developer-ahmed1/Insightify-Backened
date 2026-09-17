"""
Gamification endpoints: badges, quizzes, leaderboard.
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_active_user, get_gamification_service
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.gamification import (
    BadgeResponse, UserBadgeResponse, UserBadgesResponse,
    LeaderboardEntry, LeaderboardResponse,
    QuizResponse, QuizDetailResponse, QuizQuestionResponse,
    QuizAttemptCreate, QuizAttemptResponse, QuestionResult,
    XPEventResponse, LevelProgressResponse
)
from app.services.gamification_service import GamificationService
from app.services.user_service import UserService

router = APIRouter()


# Badge endpoints
@router.get("/badges", response_model=List[BadgeResponse])
async def get_all_badges(
    service: GamificationService = Depends(get_gamification_service),
):
    """Get all available badges."""
    badges = await service.get_all_badges()
    return [
        BadgeResponse(
            id=b.id,
            name=b.name,
            slug=b.slug,
            description=b.description,
            icon_url=b.icon_url,
            category=b.category,
            xp_reward=b.xp_reward,
        )
        for b in badges
    ]


@router.get("/badges/me", response_model=UserBadgesResponse)
async def get_my_badges(
    user: User = Depends(get_current_active_user),
    service: GamificationService = Depends(get_gamification_service),
):
    """Get current user's earned badges."""
    user_badges = await service.get_user_badges(user.id)
    return UserBadgesResponse(
        badges=[
            UserBadgeResponse(
                badge=BadgeResponse(
                    id=ub.badge.id,
                    name=ub.badge.name,
                    slug=ub.badge.slug,
                    description=ub.badge.description,
                    icon_url=ub.badge.icon_url,
                    category=ub.badge.category,
                    xp_reward=ub.badge.xp_reward,
                ),
                earned_at=ub.earned_at,
            )
            for ub in user_badges
        ],
        total=len(user_badges),
    )


# Leaderboard endpoints
@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    period: str = Query("all_time", description="daily, weekly, monthly, all_time"),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_active_user),
    service: GamificationService = Depends(get_gamification_service),
):
    """Get XP leaderboard."""
    from app.core.database import get_db
    from app.services.user_service import UserService
    from sqlalchemy.ext.asyncio import AsyncSession
    
    async for db in get_db():
        user_service = UserService(db)
        entries = await user_service.get_leaderboard(limit=limit)
        break
    
    # Find current user's rank
    current_rank = None
    for entry in entries:
        if entry["user_id"] == user.id:
            current_rank = entry["rank"]
            break
    
    return LeaderboardResponse(
        entries=[LeaderboardEntry(**e) for e in entries],
        period=period,
        current_user_rank=current_rank,
    )


# Level progress endpoint
@router.get("/level", response_model=LevelProgressResponse)
async def get_level_progress(
    user: User = Depends(get_current_active_user),
):
    """Get current user's level progress."""
    from app.services.user_service import UserService
    
    current_level = user.level
    xp_for_current = UserService(None)._xp_for_level(current_level) if current_level > 1 else 0
    xp_for_next = UserService(None).xp_for_level(current_level + 1)
    
    progress = (user.xp - xp_for_current) / (xp_for_next - xp_for_current) if xp_for_next > xp_for_current else 1.0
    
    return LevelProgressResponse(
        current_level=current_level,
        current_xp=user.xp,
        xp_for_next_level=xp_for_next,
        xp_progress=min(1.0, max(0.0, progress)),
    )


# Quiz endpoints
@router.get("/quizzes", response_model=List[QuizResponse])
async def get_quizzes(
    category_id: Optional[UUID] = None,
    difficulty: Optional[int] = Query(None, ge=1, le=5),
    service: GamificationService = Depends(get_gamification_service),
):
    """Get available quizzes."""
    quizzes = await service.get_quizzes(category_id, difficulty)
    return [
        QuizResponse(
            id=q.id,
            title=q.title,
            description=q.description,
            category_name=q.category.name if q.category else None,
            difficulty_level=q.difficulty_level,
            xp_reward=q.xp_reward,
            question_count=len(q.questions) if hasattr(q, 'questions') else 0,
            time_limit_seconds=q.time_limit_seconds,
            average_score=q.average_score,
        )
        for q in quizzes
    ]


@router.get("/quizzes/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(
    quiz_id: UUID,
    user: User = Depends(get_current_active_user),
    service: GamificationService = Depends(get_gamification_service),
):
    """Get quiz with questions (for taking the quiz)."""
    quiz = await service.get_quiz_with_questions(quiz_id)
    if not quiz:
        raise NotFoundError("Quiz", str(quiz_id))
    
    return QuizDetailResponse(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        category_name=quiz.category.name if quiz.category else None,
        difficulty_level=quiz.difficulty_level,
        xp_reward=quiz.xp_reward,
        question_count=len(quiz.questions),
        time_limit_seconds=quiz.time_limit_seconds,
        average_score=quiz.average_score,
        questions=[
            QuizQuestionResponse(
                id=q.id,
                question_type=q.question_type,
                question=q.question,
                media_url=q.media_url,
                options=q.options,
                order_index=q.order_index,
                points=q.points,
            )
            for q in sorted(quiz.questions, key=lambda x: x.order_index)
        ],
    )


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizAttemptResponse)
async def submit_quiz(
    quiz_id: UUID,
    data: QuizAttemptCreate,
    user: User = Depends(get_current_active_user),
    service: GamificationService = Depends(get_gamification_service),
):
    """Submit quiz answers and get results."""
    attempt = await service.submit_quiz_attempt(
        user_id=user.id,
        quiz_id=quiz_id,
        answers=[a.model_dump() for a in data.answers],
        time_taken=data.time_taken_seconds,
    )
    
    return QuizAttemptResponse(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        quiz_title=attempt.quiz.title,
        score=attempt.score,
        total_questions=attempt.total_questions,
        correct_answers=attempt.correct_answers,
        xp_earned=attempt.xp_earned,
        results=[
            QuestionResult(**r) for r in attempt.answers
        ],
        completed_at=attempt.completed_at,
    )
