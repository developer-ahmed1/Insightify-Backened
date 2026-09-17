"""
Gamification service for XP, badges, and quizzes.
"""
import math
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.gamification import (
    Badge, UserBadge, XPRule, Quiz, QuizQuestion, QuizAttempt
)

logger = get_logger(__name__)


class GamificationService:
    """Service for gamification features."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # XP Methods
    async def get_xp_rule(self, action: str) -> Optional[XPRule]:
        """Get XP rule by action name."""
        result = await self.db.execute(
            select(XPRule)
            .where(XPRule.action == action)
            .where(XPRule.is_active == True)
        )
        return result.scalar_one_or_none()

    async def award_xp(
        self,
        user_id: UUID,
        action: str,
        multiplier: float = 1.0,
    ) -> dict:
        """
        Award XP for an action.
        Returns dict with xp earned and level info.
        """
        rule = await self.get_xp_rule(action)
        if not rule:
            # Use default if no rule exists
            xp = 10
        else:
            xp = rule.base_xp

        # Apply multipliers
        xp = int(xp * multiplier)

        # Get user and update XP
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))

        old_level = user.level
        user.xp += xp
        user.level = self._calculate_level(user.xp)
        
        level_up = user.level > old_level

        await self.db.flush()

        # Check for badge unlocks
        await self._check_badge_unlocks(user_id)

        return {
            "action": action,
            "xp_earned": xp,
            "new_total_xp": user.xp,
            "new_level": user.level,
            "level_up": level_up,
        }

    def _calculate_level(self, xp: int) -> int:
        """Calculate level from XP."""
        if xp < 100:
            return 1
        return min(100, int(math.log(xp / 100, 1.5)) + 2)

    def _xp_for_level(self, level: int) -> int:
        """Get XP required for a level."""
        if level <= 1:
            return 100
        return int(100 * (1.5 ** (level - 1)))

    # Badge Methods
    async def get_all_badges(self) -> List[Badge]:
        """Get all active badges."""
        result = await self.db.execute(
            select(Badge)
            .where(Badge.is_active == True)
            .where(Badge.is_hidden == False)
            .order_by(Badge.category, Badge.name)
        )
        return result.scalars().all()

    async def get_user_badges(self, user_id: UUID) -> List[UserBadge]:
        """Get all badges earned by user."""
        result = await self.db.execute(
            select(UserBadge)
            .options(selectinload(UserBadge.badge))
            .where(UserBadge.user_id == user_id)
            .order_by(UserBadge.earned_at.desc())
        )
        return result.scalars().all()

    async def award_badge(self, user_id: UUID, badge_id: UUID) -> Optional[UserBadge]:
        """Award a badge to user (if not already earned)."""
        # Check if already earned
        existing = await self.db.execute(
            select(UserBadge)
            .where(UserBadge.user_id == user_id)
            .where(UserBadge.badge_id == badge_id)
        )
        if existing.scalar_one_or_none():
            return None

        # Get badge for XP reward
        badge = await self.db.get(Badge, badge_id)
        if not badge:
            return None

        user_badge = UserBadge(
            user_id=user_id,
            badge_id=badge_id,
        )
        self.db.add(user_badge)

        # Award XP if badge has reward
        if badge.xp_reward > 0:
            await self.award_xp(user_id, "badge_earned", multiplier=badge.xp_reward/10)

        await self.db.flush()
        
        logger.info(f"Badge awarded: {badge.name} to user {user_id}")
        return user_badge

    async def _check_badge_unlocks(self, user_id: UUID) -> None:
        """Check and award any unlocked badges."""
        # Get user stats
        user = await self.db.get(User, user_id)
        if not user:
            return

        # Get badges with criteria
        result = await self.db.execute(
            select(Badge)
            .where(Badge.is_active == True)
            .where(Badge.criteria.isnot(None))
        )
        badges = result.scalars().all()

        for badge in badges:
            if not badge.criteria:
                continue

            # Check if already earned
            existing = await self.db.execute(
                select(UserBadge)
                .where(UserBadge.user_id == user_id)
                .where(UserBadge.badge_id == badge.id)
            )
            if existing.scalar_one_or_none():
                continue

            # Evaluate criteria
            if await self._evaluate_criteria(user_id, badge.criteria):
                await self.award_badge(user_id, badge.id)

    async def _evaluate_criteria(self, user_id: UUID, criteria: dict) -> bool:
        """Evaluate badge criteria."""
        criteria_type = criteria.get("type")
        field = criteria.get("field")
        threshold = criteria.get("threshold", 0)

        if criteria_type == "xp":
            user = await self.db.get(User, user_id)
            return user and user.xp >= threshold

        elif criteria_type == "level":
            user = await self.db.get(User, user_id)
            return user and user.level >= threshold

        elif criteria_type == "count":
            if field == "detections":
                from app.models.detection import Detection
                count = await self.db.scalar(
                    select(func.count(Detection.id))
                    .where(Detection.user_id == user_id)
                )
                return (count or 0) >= threshold

            elif field == "posts":
                from app.models.community import Post
                count = await self.db.scalar(
                    select(func.count(Post.id))
                    .where(Post.user_id == user_id)
                    .where(Post.deleted_at.is_(None))
                )
                return (count or 0) >= threshold

        return False

    # Quiz Methods
    async def get_quizzes(
        self,
        category_id: Optional[UUID] = None,
        difficulty: Optional[int] = None,
    ) -> List[Quiz]:
        """Get available quizzes."""
        query = (
            select(Quiz)
            .where(Quiz.is_active == True)
            .order_by(Quiz.difficulty_level, Quiz.title)
        )

        if category_id:
            query = query.where(Quiz.category_id == category_id)
        if difficulty:
            query = query.where(Quiz.difficulty_level == difficulty)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_quiz_with_questions(self, quiz_id: UUID) -> Optional[Quiz]:
        """Get quiz with all questions."""
        result = await self.db.execute(
            select(Quiz)
            .options(selectinload(Quiz.questions))
            .where(Quiz.id == quiz_id)
            .where(Quiz.is_active == True)
        )
        return result.scalar_one_or_none()

    async def submit_quiz_attempt(
        self,
        user_id: UUID,
        quiz_id: UUID,
        answers: List[dict],
        time_taken: Optional[int] = None,
    ) -> QuizAttempt:
        """Submit and grade a quiz attempt."""
        quiz = await self.get_quiz_with_questions(quiz_id)
        if not quiz:
            raise NotFoundError("Quiz", str(quiz_id))

        # Build question lookup
        questions = {str(q.id): q for q in quiz.questions}
        
        # Grade answers
        results = []
        correct = 0
        total = len(quiz.questions)

        for answer in answers:
            question_id = str(answer.get("question_id"))
            user_answer = answer.get("answer", "")
            
            question = questions.get(question_id)
            if not question:
                continue

            is_correct = user_answer.lower().strip() == question.correct_answer.lower().strip()
            if is_correct:
                correct += 1

            results.append({
                "question_id": question_id,
                "user_answer": user_answer,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "explanation": question.explanation,
            })

        # Calculate score and XP
        score = int((correct / total) * 100) if total > 0 else 0
        xp_earned = int(quiz.xp_reward * (correct / total)) if total > 0 else 0

        # Create attempt record
        attempt = QuizAttempt(
            user_id=user_id,
            quiz_id=quiz_id,
            score=score,
            total_questions=total,
            correct_answers=correct,
            xp_earned=xp_earned,
            answers=results,
            time_taken_seconds=time_taken,
            completed_at=datetime.utcnow(),
        )

        self.db.add(attempt)

        # Award XP
        if xp_earned > 0:
            await self.award_xp(user_id, "quiz_completed", multiplier=xp_earned/10)

        # Update quiz stats
        quiz.total_attempts += 1
        quiz.average_score = (
            (quiz.average_score * (quiz.total_attempts - 1) + score) 
            / quiz.total_attempts
        )

        await self.db.flush()

        logger.info(
            f"Quiz attempt: user={user_id} quiz={quiz_id} "
            f"score={score}% ({correct}/{total})"
        )

        return attempt

    async def get_user_quiz_attempts(
        self,
        user_id: UUID,
        quiz_id: Optional[UUID] = None,
    ) -> List[QuizAttempt]:
        """Get user's quiz attempts."""
        query = (
            select(QuizAttempt)
            .options(selectinload(QuizAttempt.quiz))
            .where(QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.created_at.desc())
        )

        if quiz_id:
            query = query.where(QuizAttempt.quiz_id == quiz_id)

        result = await self.db.execute(query)
        return result.scalars().all()
