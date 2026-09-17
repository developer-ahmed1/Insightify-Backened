"""
Gamification schemas — RFC §11 Quiz, §12 Leaderboard, §13 Achievements.
"""
from datetime import datetime
from typing import List, Optional, Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


# ===========================================================================
# §11 Quiz & Education
# ===========================================================================

class QuizCategoryResponse(BaseSchema):
    """Quiz category for the category selector. RFC §11.1."""
    id: str
    name: str
    slug: str
    quizCount: int = 0
    iconUrl: Optional[str] = None


class QuizListItemResponse(BaseSchema):
    """Quiz list item. RFC §11.1."""
    id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty: str = "Beginner"  # Beginner | Intermediate | Advanced
    questionCount: int = 0
    xpReward: int = 50
    averageScore: float = 0.0
    timeLimitSeconds: Optional[int] = None
    isFeatured: bool = False


class QuizQuestionResponse(BaseSchema):
    """Quiz question (without correct answer). RFC §11.2."""
    id: str
    questionType: str = "mcq"  # mcq | true_false | image_identify
    question: str
    mediaUrl: Optional[str] = None
    options: List[str] = []
    orderIndex: int = 0
    points: int = 10


class QuizDetailResponse(QuizListItemResponse):
    """Quiz with questions for taking the quiz. RFC §11.2."""
    questions: List[QuizQuestionResponse] = []


class QuizAnswerSubmit(BaseSchema):
    """Single answer in a quiz attempt."""
    questionId: str
    answer: str
    timeMs: Optional[int] = None


class QuizAttemptRequest(BaseSchema):
    """Submit quiz attempt. RFC §11.4."""
    quizId: str
    answers: List[QuizAnswerSubmit]
    timeTakenSeconds: Optional[int] = None


class QuestionResultResponse(BaseSchema):
    """Result for a single question."""
    questionId: str
    question: str
    userAnswer: str
    correctAnswer: str
    isCorrect: bool
    explanation: Optional[str] = None


class QuizAttemptResultResponse(BaseSchema):
    """Quiz attempt result. RFC §11.5."""
    id: str
    quizId: str
    quizTitle: str
    score: int
    totalQuestions: int
    correctAnswers: int
    xpEarned: int
    results: List[QuestionResultResponse] = []
    completedAt: str


# §11.3 Daily Challenge
class DailyChallengeResponse(BaseSchema):
    """Daily quiz challenge. RFC §11.3."""
    id: str
    quizId: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    rewardXp: int = 50
    timeRemainingSeconds: int = 0


# ===========================================================================
# §12 Leaderboard
# ===========================================================================

class LeaderboardEntryResponse(BaseSchema):
    """Single leaderboard entry. RFC §12.1."""
    rank: int
    userId: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    score: int = 0
    level: int = 1
    isCurrentUser: bool = False


class LeaderboardResponse(BaseSchema):
    """Leaderboard with period filter. RFC §12.1."""
    period: str = "daily"  # daily | weekly | monthly | all_time
    entries: List[LeaderboardEntryResponse] = []
    currentUserRank: Optional[int] = None


# ===========================================================================
# §13 Achievements
# ===========================================================================

class AchievementResponse(BaseSchema):
    """Achievement/badge item. RFC §13.1."""
    id: str
    title: str
    description: Optional[str] = None
    iconName: Optional[str] = None
    iconColor: Optional[str] = None
    iconUrl: Optional[str] = None
    category: str = "detection"
    xpReward: int = 0
    unlocked: bool = False
    unlockedDate: Optional[str] = None
    currentProgress: int = 0
    targetProgress: int = 1


class AchievementsListResponse(BaseSchema):
    """Full achievement list. RFC §13.1."""
    achievements: List[AchievementResponse] = []
    totalUnlocked: int = 0
    totalLocked: int = 0


# ===========================================================================
# XP Events
# ===========================================================================

class XPEventResponse(BaseSchema):
    """XP award event."""
    action: str
    xpEarned: int
    newTotalXp: int
    newLevel: int
    levelUp: bool = False


class LevelProgressResponse(BaseSchema):
    """User's level progress."""
    currentLevel: int
    currentXp: int
    xpForNextLevel: int
    xpProgress: float  # 0.0 to 1.0


# ===========================================================================
# Legacy schemas (backward compatibility)
# ===========================================================================

class BadgeResponse(BaseSchema):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    category: str
    xp_reward: int


class UserBadgeResponse(BaseSchema):
    badge: BadgeResponse
    earned_at: datetime


class UserBadgesResponse(BaseSchema):
    badges: List[UserBadgeResponse]
    total: int


class LeaderboardEntry(BaseSchema):
    rank: int
    user_id: UUID
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    xp: int
    level: int


class QuizResponse(BaseSchema):
    id: UUID
    title: str
    description: Optional[str] = None
    category_name: Optional[str] = None
    difficulty_level: int
    xp_reward: int
    question_count: int
    time_limit_seconds: Optional[int] = None
    average_score: float = 0.0


class QuizDetailOldResponse(QuizResponse):
    questions: List[Any]


class QuizAttemptCreate(BaseSchema):
    quiz_id: UUID
    answers: List[Any]
    time_taken_seconds: Optional[int] = None


class QuizAttemptResponse(BaseSchema):
    id: UUID
    quiz_id: UUID
    quiz_title: str
    score: int
    total_questions: int
    correct_answers: int
    xp_earned: int
    results: List[Any] = []
    completed_at: datetime
