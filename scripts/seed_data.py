"""
Seed data script for initial setup.
Creates default categories, badges, XP rules, and sample quizzes.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import async_session_maker, init_db
from app.models.detection import ScamCategory
from app.models.gamification import Badge, XPRule, Quiz, QuizQuestion
from app.models.monetization import SubscriptionPlan


async def seed_categories():
    """Seed scam categories."""
    categories = [
        {
            "name": "Phishing",
            "slug": "phishing",
            "description": "Fake emails, texts, or websites designed to steal personal information",
            "severity_level": 8,
        },
        {
            "name": "Tech Support",
            "slug": "tech-support",
            "description": "Fake tech support calls or pop-ups claiming your computer is infected",
            "severity_level": 7,
        },
        {
            "name": "Romance Scam",
            "slug": "romance",
            "description": "Fake romantic interest to manipulate victims into sending money",
            "severity_level": 9,
        },
        {
            "name": "Investment Fraud",
            "slug": "investment",
            "description": "Fake investment opportunities promising unrealistic returns",
            "severity_level": 9,
        },
        {
            "name": "Lottery/Prize",
            "slug": "lottery",
            "description": "Fake lottery winnings or prize notifications",
            "severity_level": 6,
        },
        {
            "name": "Impersonation",
            "slug": "impersonation",
            "description": "Scammers pretending to be government officials, relatives, or companies",
            "severity_level": 8,
        },
        {
            "name": "Online Shopping",
            "slug": "shopping",
            "description": "Fake online stores or sellers",
            "severity_level": 6,
        },
        {
            "name": "Job Scam",
            "slug": "job",
            "description": "Fake job offers requiring upfront payments",
            "severity_level": 7,
        },
    ]
    
    async with async_session_maker() as session:
        for cat_data in categories:
            existing = await session.execute(
                select(ScamCategory).where(ScamCategory.slug == cat_data["slug"])
            )
            if not existing.scalar_one_or_none():
                category = ScamCategory(**cat_data)
                session.add(category)
        await session.commit()
        print(f"✓ Seeded {len(categories)} scam categories")


async def seed_badges():
    """Seed achievement badges."""
    badges = [
        # Detection badges
        {"name": "First Detection", "slug": "first-detection", "category": "detection", 
         "description": "Complete your first scam detection", "xp_reward": 50,
         "criteria": {"type": "count", "field": "detections", "threshold": 1}},
        {"name": "Scam Spotter", "slug": "scam-spotter", "category": "detection",
         "description": "Detect 10 scams", "xp_reward": 100,
         "criteria": {"type": "count", "field": "detections", "threshold": 10}},
        {"name": "Guardian", "slug": "guardian", "category": "detection",
         "description": "Detect 100 scams", "xp_reward": 500,
         "criteria": {"type": "count", "field": "detections", "threshold": 100}},
        
        # Community badges
        {"name": "First Post", "slug": "first-post", "category": "community",
         "description": "Create your first post", "xp_reward": 25,
         "criteria": {"type": "count", "field": "posts", "threshold": 1}},
        {"name": "Contributor", "slug": "contributor", "category": "community",
         "description": "Create 10 posts", "xp_reward": 100,
         "criteria": {"type": "count", "field": "posts", "threshold": 10}},
        {"name": "Top Contributor", "slug": "top-contributor", "category": "community",
         "description": "Create 50 posts", "xp_reward": 300,
         "criteria": {"type": "count", "field": "posts", "threshold": 50}},
        
        # Level badges
        {"name": "Rising Star", "slug": "rising-star", "category": "level",
         "description": "Reach level 5", "xp_reward": 100,
         "criteria": {"type": "level", "threshold": 5}},
        {"name": "Expert", "slug": "expert", "category": "level",
         "description": "Reach level 10", "xp_reward": 200,
         "criteria": {"type": "level", "threshold": 10}},
        {"name": "Master", "slug": "master", "category": "level",
         "description": "Reach level 25", "xp_reward": 500,
         "criteria": {"type": "level", "threshold": 25}},
        
        # Streak badges
        {"name": "Week Warrior", "slug": "week-warrior", "category": "streak",
         "description": "Maintain a 7-day streak", "xp_reward": 70},
        {"name": "Streak Master", "slug": "streak-master", "category": "streak",
         "description": "Maintain a 30-day streak", "xp_reward": 300},
    ]
    
    async with async_session_maker() as session:
        for badge_data in badges:
            existing = await session.execute(
                select(Badge).where(Badge.slug == badge_data["slug"])
            )
            if not existing.scalar_one_or_none():
                badge = Badge(**badge_data)
                session.add(badge)
        await session.commit()
        print(f"✓ Seeded {len(badges)} badges")


async def seed_xp_rules():
    """Seed XP award rules."""
    rules = [
        {"action": "detection_text", "base_xp": 10, "description": "Complete text detection"},
        {"action": "detection_audio", "base_xp": 15, "description": "Complete audio detection"},
        {"action": "detection_video", "base_xp": 20, "description": "Complete video detection"},
        {"action": "post_created", "base_xp": 20, "daily_limit": 5, "description": "Create a post"},
        {"action": "comment_created", "base_xp": 5, "daily_limit": 20, "description": "Write a comment"},
        {"action": "post_liked", "base_xp": 25, "description": "Your post received a like"},
        {"action": "quiz_completed", "base_xp": 50, "description": "Complete a quiz"},
        {"action": "daily_login", "base_xp": 5, "daily_limit": 1, "description": "Daily login bonus"},
        {"action": "badge_earned", "base_xp": 0, "description": "Badge XP (handled separately)"},
    ]
    
    async with async_session_maker() as session:
        for rule_data in rules:
            existing = await session.execute(
                select(XPRule).where(XPRule.action == rule_data["action"])
            )
            if not existing.scalar_one_or_none():
                rule = XPRule(**rule_data)
                session.add(rule)
        await session.commit()
        print(f"✓ Seeded {len(rules)} XP rules")


async def seed_subscription_plans():
    """Seed subscription plans."""
    plans = [
        {
            "name": "Free",
            "slug": "free",
            "description": "Basic scam detection",
            "price_monthly": 0,
            "price_yearly": 0,
            "detection_limit_daily": 10,
            "history_retention_days": 7,
            "features": {
                "text_detections_daily": 10,
                "audio_detections_daily": 3,
                "video_detections_daily": 0,
                "show_ads": True,
                "xp_multiplier": 1.0,
            },
        },
        {
            "name": "Premium",
            "slug": "premium",
            "description": "Enhanced protection for individuals",
            "price_monthly": 4.99,
            "price_yearly": 49.99,
            "detection_limit_daily": 100,
            "history_retention_days": 90,
            "is_popular": True,
            "features": {
                "text_detections_daily": 100,
                "audio_detections_daily": 50,
                "video_detections_daily": 20,
                "show_ads": False,
                "xp_multiplier": 1.5,
                "extended_history": True,
                "priority_support": True,
            },
        },
        {
            "name": "Premium+",
            "slug": "premium-plus",
            "description": "Maximum protection for power users",
            "price_monthly": 9.99,
            "price_yearly": 99.99,
            "detection_limit_daily": 999999,
            "history_retention_days": 365,
            "features": {
                "text_detections_daily": 999999,
                "audio_detections_daily": 999999,
                "video_detections_daily": 999999,
                "show_ads": False,
                "xp_multiplier": 2.0,
                "extended_history": True,
                "priority_support": True,
                "early_access": True,
            },
        },
    ]
    
    async with async_session_maker() as session:
        for idx, plan_data in enumerate(plans):
            existing = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.slug == plan_data["slug"])
            )
            if not existing.scalar_one_or_none():
                plan = SubscriptionPlan(**plan_data, sort_order=idx)
                session.add(plan)
        await session.commit()
        print(f"✓ Seeded {len(plans)} subscription plans")


async def seed_sample_quiz():
    """Seed a sample quiz."""
    async with async_session_maker() as session:
        # Check if already exists
        existing = await session.execute(
            select(Quiz).where(Quiz.title == "Phishing 101")
        )
        if existing.scalar_one_or_none():
            print("✓ Sample quiz already exists")
            return
        
        # Get phishing category
        cat_result = await session.execute(
            select(ScamCategory).where(ScamCategory.slug == "phishing")
        )
        category = cat_result.scalar_one_or_none()
        
        quiz = Quiz(
            title="Phishing 101",
            description="Learn to identify common phishing attempts",
            category_id=category.id if category else None,
            difficulty_level=1,
            xp_reward=50,
        )
        session.add(quiz)
        await session.flush()
        
        questions = [
            {
                "question": "Which of the following is a common sign of a phishing email?",
                "options": [
                    "Company logo in the email",
                    "Urgent language demanding immediate action",
                    "The email comes from a known contact",
                    "The email has correct grammar"
                ],
                "correct_answer": "Urgent language demanding immediate action",
                "explanation": "Phishing emails often create urgency to prevent you from thinking critically.",
            },
            {
                "question": "What should you do if you receive a suspicious email asking for your password?",
                "options": [
                    "Reply with your password",
                    "Click the link to verify",
                    "Contact the company directly through their official website",
                    "Forward it to your friends"
                ],
                "correct_answer": "Contact the company directly through their official website",
                "explanation": "Always verify requests through official channels, never through links in emails.",
            },
            {
                "question": "True or False: Banks regularly ask customers to verify account information via email.",
                "options": ["True", "False"],
                "correct_answer": "False",
                "explanation": "Legitimate financial institutions never ask for sensitive information via email.",
            },
        ]
        
        for idx, q_data in enumerate(questions):
            question = QuizQuestion(
                quiz_id=quiz.id,
                question_type="mcq",
                question=q_data["question"],
                options=q_data["options"],
                correct_answer=q_data["correct_answer"],
                explanation=q_data["explanation"],
                order_index=idx,
            )
            session.add(question)
        
        await session.commit()
        print("✓ Seeded sample quiz with 3 questions")


async def main():
    """Run all seed functions."""
    print("\n🌱 Seeding database...\n")
    
    await seed_categories()
    await seed_badges()
    await seed_xp_rules()
    await seed_subscription_plans()
    await seed_sample_quiz()
    
    print("\n✅ Seeding complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
