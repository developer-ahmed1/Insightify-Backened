"""
Quiz & Education API endpoints — RFC §11 Quiz.

GET  /api/v1/quiz                     — §11.1 Get Quiz List
GET  /api/v1/quiz/categories          — §11.1 Get Quiz Categories
GET  /api/v1/quiz/daily-challenge     — §11.3 Get Daily Challenge
GET  /api/v1/quiz/{quizId}            — §11.2 Get Quiz Detail + Questions
POST /api/v1/quiz/{quizId}/attempt    — §11.4 Submit Quiz Attempt
"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.models.detection import ScamCategory
from app.models.gamification import Quiz, QuizQuestion, QuizAttempt
from app.models.daily_challenge import DailyChallenge
from app.schemas.gamification import (
    QuizCategoryResponse,
    QuizListItemResponse,
    QuizDetailResponse,
    QuizQuestionResponse,
    QuizAttemptRequest,
    QuizAttemptResultResponse,
    QuestionResultResponse,
    DailyChallengeResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])


# ---------------------------------------------------------------------------
# §11.1 Get Quiz List
# ---------------------------------------------------------------------------
@router.get("", response_model=list[QuizListItemResponse])
async def get_quiz_list(
    difficulty: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of available quizzes."""
    query = select(Quiz).options(selectinload(Quiz.category)).where(Quiz.is_active == True)

    if difficulty and difficulty.lower() != "all":
        diff_map = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4, "master": 5}
        diff_level = diff_map.get(difficulty.lower())
        if diff_level:
            query = query.where(Quiz.difficulty_level == diff_level)

    if category and category.lower() != "all":
        if category.lower() == "general":
            query = query.where(Quiz.category_id == None)
        else:
            query = query.outerjoin(ScamCategory, Quiz.category_id == ScamCategory.id)
            query = query.where(ScamCategory.name.ilike(f"%{category}%"))

    query = query.order_by(Quiz.is_featured.desc(), Quiz.created_at.desc())
    result = await db.execute(query)
    quizzes = result.scalars().all()

    diff_labels = {1: "Beginner", 2: "Intermediate", 3: "Advanced", 4: "Expert", 5: "Master"}

    items = []
    for q in quizzes:
        q_count = await db.scalar(
            select(func.count()).where(QuizQuestion.quiz_id == q.id)
        ) or 0
        items.append(QuizListItemResponse(
            id=str(q.id),
            title=q.title,
            description=q.description,
            category=q.category.name if q.category else None,
            difficulty=diff_labels.get(q.difficulty_level, "Beginner"),
            questionCount=q_count,
            xpReward=q.xp_reward,
            averageScore=q.average_score,
            timeLimitSeconds=q.time_limit_seconds,
            isFeatured=q.is_featured,
        ))

    return items


# ---------------------------------------------------------------------------
# §11.1 Get Quiz Categories
# ---------------------------------------------------------------------------
@router.get("/categories", response_model=list[QuizCategoryResponse])
async def get_quiz_categories(db: AsyncSession = Depends(get_db)):
    """Get quiz categories with counts."""
    result = await db.execute(
        select(ScamCategory).where(ScamCategory.is_active == True)
    )
    categories = result.scalars().all()

    items = []
    for cat in categories:
        quiz_count = await db.scalar(
            select(func.count()).where(Quiz.category_id == cat.id).where(Quiz.is_active == True)
        ) or 0
        items.append(QuizCategoryResponse(
            id=str(cat.id),
            name=cat.name,
            slug=cat.slug,
            quizCount=quiz_count,
            iconUrl=cat.icon_url,
        ))

    return items


# ---------------------------------------------------------------------------
# §11.3 Get Daily Challenge
# ---------------------------------------------------------------------------
@router.get("/daily-challenge", response_model=DailyChallengeResponse)
async def get_daily_challenge(db: AsyncSession = Depends(get_db)):
    """Get today's daily challenge."""
    today = date.today()
    result = await db.execute(
        select(DailyChallenge)
        .where(DailyChallenge.active_date == today)
        .where(DailyChallenge.is_active == True)
    )
    challenge = result.scalar_one_or_none()

    if not challenge:
        # Fallback: return a default challenge
        return DailyChallengeResponse(
            id="default",
            quizId=None,
            title="No Challenge Today",
            subtitle="Check back tomorrow for a new challenge!",
            rewardXp=0,
            timeRemainingSeconds=0,
        )

    # Calculate time remaining until midnight
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=23, minute=59, second=59)
    remaining = max(0, int((midnight - now).total_seconds()))

    return DailyChallengeResponse(
        id=str(challenge.id),
        quizId=str(challenge.quiz_id) if challenge.quiz_id else None,
        title=challenge.title,
        subtitle=challenge.subtitle,
        rewardXp=challenge.reward_xp,
        timeRemainingSeconds=remaining,
    )


# ---------------------------------------------------------------------------
# §11.2 Get Quiz Detail + Questions
# ---------------------------------------------------------------------------
@router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz_detail(
    quiz_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get quiz with all questions (without correct answers)."""
    quiz = None
    try:
        quiz_uuid = UUID(quiz_id)
        result = await db.execute(
            select(Quiz).options(selectinload(Quiz.category)).where(Quiz.id == quiz_uuid).where(Quiz.is_active == True)
        )
        quiz = result.scalar_one_or_none()
    except (ValueError, TypeError):
        # Allow fallback lookup by title if a slug/name was passed
        slug_clean = quiz_id.replace("-", " ")
        result = await db.execute(
            select(Quiz).options(selectinload(Quiz.category)).where(Quiz.title.ilike(f"%{slug_clean}%")).where(Quiz.is_active == True)
        )
        quiz = result.scalars().first()
        if not quiz:
            # Fallback to first active quiz
            result = await db.execute(
                select(Quiz).options(selectinload(Quiz.category)).where(Quiz.is_active == True)
            )
            quiz = result.scalars().first()

    if not quiz:
        raise NotFoundError("Quiz", quiz_id)

    # Fetch questions
    q_result = await db.execute(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.order_index)
    )
    questions = q_result.scalars().all()

    diff_labels = {1: "Beginner", 2: "Intermediate", 3: "Advanced", 4: "Expert", 5: "Master"}

    return QuizDetailResponse(
        id=str(quiz.id),
        title=quiz.title,
        description=quiz.description,
        category=quiz.category.name if quiz.category else None,
        difficulty=diff_labels.get(quiz.difficulty_level, "Beginner"),
        questionCount=len(questions),
        xpReward=quiz.xp_reward,
        averageScore=quiz.average_score,
        timeLimitSeconds=quiz.time_limit_seconds,
        isFeatured=quiz.is_featured,
        questions=[
            QuizQuestionResponse(
                id=str(q.id),
                questionType=q.question_type,
                question=q.question,
                mediaUrl=q.media_url,
                options=q.options or [],
                orderIndex=q.order_index,
                points=q.points,
            )
            for q in questions
        ],
    )


# ---------------------------------------------------------------------------
# §11.4 Submit Quiz Attempt
# ---------------------------------------------------------------------------
@router.post("/{quiz_id}/attempt", response_model=QuizAttemptResultResponse)
async def submit_quiz_attempt(
    quiz_id: str,
    request: QuizAttemptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit answers and get graded results."""
    try:
        quiz_uuid = UUID(quiz_id)
    except (ValueError, TypeError):
        raise NotFoundError("Quiz", quiz_id)

    result = await db.execute(select(Quiz).where(Quiz.id == quiz_uuid))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise NotFoundError("Quiz", quiz_id)

    # Fetch questions for grading
    q_result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)
    )
    questions = {str(q.id): q for q in q_result.scalars().all()}

    # Grade answers
    question_results = []
    correct_count = 0
    total_score = 0

    for answer in request.answers:
        q = questions.get(answer.questionId)
        if not q:
            continue
        is_correct = answer.answer == q.correct_answer
        if is_correct:
            correct_count += 1
            total_score += q.points

        question_results.append(QuestionResultResponse(
            questionId=answer.questionId,
            question=q.question,
            userAnswer=answer.answer,
            correctAnswer=q.correct_answer,
            isCorrect=is_correct,
            explanation=q.explanation,
        ))

    # Calculate XP
    total_questions = len(questions)
    score_pct = (correct_count / total_questions * 100) if total_questions > 0 else 0
    xp_earned = int(quiz.xp_reward * (score_pct / 100))

    # Save attempt
    now = datetime.now(timezone.utc)
    attempt = QuizAttempt(
        user_id=user.id,
        quiz_id=quiz.id,
        score=total_score,
        total_questions=total_questions,
        correct_answers=correct_count,
        xp_earned=xp_earned,
        answers=[a.model_dump() for a in request.answers],
        time_taken_seconds=request.timeTakenSeconds,
        completed_at=now,
    )
    db.add(attempt)

    # Award XP
    user.xp += xp_earned
    # Check level up
    while user.xp >= user.next_level_xp:
        user.level += 1

    # Update quiz stats
    quiz.total_attempts += 1
    quiz.average_score = (
        (quiz.average_score * (quiz.total_attempts - 1) + score_pct) / quiz.total_attempts
    )

    await db.flush()

    return QuizAttemptResultResponse(
        id=str(attempt.id),
        quizId=str(quiz.id),
        quizTitle=quiz.title,
        score=total_score,
        totalQuestions=total_questions,
        correctAnswers=correct_count,
        xpEarned=xp_earned,
        results=question_results,
        completedAt=now.isoformat(),
    )
