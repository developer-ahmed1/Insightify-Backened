"""
Seed additional application data: Threat Posts, Daily Challenge, Daily Safety Tip, and Demo Users.
"""
import asyncio
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.security import hash_password
from app.models.user import User, UserStreak
from app.models.threat_post import ThreatPost
from app.models.daily_challenge import DailyChallenge
from app.models.daily_tip import DailySafetyTip
from app.models.gamification import Quiz


async def seed_users():
    """Seed test and leaderboard demo users."""
    demo_users = [
        {
            "email": "test@insightify.com",
            "name": "Test User",
            "display_name": "Test User",
            "username": "test_user",
            "password": "Password123!",
            "xp": 450,
            "level": 3,
            "title": "Digital Safety Guardian",
            "bio": "Protecting digital decisions with Insightify",
        },
        {
            "email": "hasan@insightify.com",
            "name": "Hasan Sajjad",
            "display_name": "Hasan Sajjad",
            "username": "hasan_s",
            "password": "Password123!",
            "xp": 1800,
            "level": 5,
            "title": "Threat Hunter",
            "bio": "Security enthusiast & active reporter",
        },
        {
            "email": "masuma@insightify.com",
            "name": "Masuma",
            "display_name": "Masuma",
            "username": "masuma_sec",
            "password": "Password123!",
            "xp": 1490,
            "level": 4,
            "title": "Awareness Advocate",
            "bio": "Helping friends avoid scams",
        },
        {
            "email": "tanim@insightify.com",
            "name": "Tanim",
            "display_name": "Tanim",
            "username": "tanim_dev",
            "password": "Password123!",
            "xp": 1205,
            "level": 4,
            "title": "Cyber Shield",
            "bio": "Spotting digital deception early",
        },
    ]

    async with async_session_maker() as session:
        for u_data in demo_users:
            existing = await session.execute(
                select(User).where(User.email == u_data["email"])
            )
            if not existing.scalar_one_or_none():
                user = User(
                    email=u_data["email"],
                    name=u_data["name"],
                    display_name=u_data["display_name"],
                    username=u_data["username"],
                    password_hash=hash_password(u_data["password"]),
                    xp=u_data["xp"],
                    level=u_data["level"],
                    title=u_data["title"],
                    bio=u_data["bio"],
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                streak = UserStreak(user_id=user.id, current_streak=5, longest_streak=12)
                session.add(streak)
        await session.commit()
        print("Users and leaderboard seeded successfully.")


async def seed_threat_posts():
    """Seed sample threat feed posts."""
    posts = [
        {
            "risk_level": "HIGH",
            "title": "Fake Banking SMS Circulating Again",
            "description": "Multiple users reported this SMS impersonating commercial banks to steal OTPs and passwords.",
            "category": "Banking",
            "platform_tag": "SMS",
            "location": "Pakistan",
            "report_count": 124,
            "view_count": 512,
            "is_verified": True,
            "is_published": True,
            "is_featured": True,
            "what_is_happening": "Attackers are sending SMS messages claiming your debit card has been blocked and instructing you to verify via a spoofed banking link.",
            "example_content": {
                "type": "sms",
                "prefix": "Dear customer, your card is suspended due to security reasons. Verify now at ",
                "link": "bit.ly/bank-auth-99",
            },
            "safety_tips": [
                "Do not click links received in SMS messages.",
                "Banks never ask for your PIN, OTP, or passwords.",
                "Call the number printed on the back of your card if in doubt.",
            ],
            "reported_by": {
                "name": "Insightify Threat Intel",
                "badge": "Verified",
                "role": "Security Researcher",
            },
        },
        {
            "risk_level": "MEDIUM",
            "title": "Phishing Ads on Social Media",
            "description": "Sponsored posts advertising 90% discounts directing users to credential-harvesting clone sites.",
            "category": "Phishing",
            "platform_tag": "Facebook",
            "location": "Global",
            "report_count": 89,
            "view_count": 340,
            "is_verified": True,
            "is_published": True,
            "is_featured": False,
            "what_is_happening": "Fraudulent ads offer heavily discounted electronics to harvest credit card information.",
            "example_content": {
                "type": "link",
                "prefix": "Exclusive 90% flash sale! Grab your iPhone before stocks end: ",
                "link": "https://discount-apple-store-promo.net",
            },
            "safety_tips": [
                "Check the official store domain name carefully.",
                "If a deal looks too good to be true, it almost certainly is.",
            ],
            "reported_by": {
                "name": "Community Alert",
                "badge": "Community",
                "role": "Moderator",
            },
        },
        {
            "risk_level": "HIGH",
            "title": "AI Voice Cloning Emergency Call",
            "description": "Scammers using 3-second audio clips to clone relatives' voices and demand immediate bail transfers.",
            "category": "Voice AI",
            "platform_tag": "Voice AI",
            "location": "Global",
            "report_count": 45,
            "view_count": 210,
            "is_verified": True,
            "is_published": True,
            "is_featured": True,
            "what_is_happening": "Attackers synthesize the voice of a family member claiming they have been arrested or in an accident, demanding instant crypto or wire transfers.",
            "safety_tips": [
                "Establish a family safe word that cannot be guessed.",
                "Hang up and call the relative directly on their known phone number.",
            ],
            "reported_by": {
                "name": "Insightify Research",
                "badge": "Verified",
                "role": "Threat Specialist",
            },
        },
    ]

    async with async_session_maker() as session:
        for p_data in posts:
            existing = await session.execute(
                select(ThreatPost).where(ThreatPost.title == p_data["title"])
            )
            if not existing.scalar_one_or_none():
                post = ThreatPost(**p_data)
                session.add(post)
        await session.commit()
        print("Threat feed posts seeded successfully.")


async def seed_daily_challenge_and_tip():
    """Seed today's daily challenge and daily safety tip."""
    today = date.today()

    async with async_session_maker() as session:
        # Get first quiz
        quiz_res = await session.execute(select(Quiz).limit(1))
        quiz = quiz_res.scalar_one_or_none()

        # Daily Challenge
        existing_dc = await session.execute(
            select(DailyChallenge).where(DailyChallenge.active_date == today)
        )
        if not existing_dc.scalar_one_or_none():
            dc = DailyChallenge(
                quiz_id=quiz.id if quiz else None,
                title="Spot the Real Banking Link",
                subtitle="Can you distinguish a genuine banking URL from an impersonator?",
                reward_xp=50,
                active_date=today,
                is_active=True,
            )
            session.add(dc)
            print("Daily challenge seeded.")

        # Daily Tip
        existing_tip = await session.execute(
            select(DailySafetyTip).where(DailySafetyTip.active_date == today)
        )
        if not existing_tip.scalar_one_or_none():
            tip = DailySafetyTip(
                title="Never Share One-Time Passwords (OTPs)",
                content="Legitimate institutions and banks will never ask for your OTP or password over phone or SMS. Keep them private!",
                category="credential_safety",
                active_date=today,
                is_active=True,
            )
            session.add(tip)
            print("Daily safety tip seeded.")

        await session.commit()


async def main():
    print("Seeding application data...")
    await seed_users()
    await seed_threat_posts()
    await seed_daily_challenge_and_tip()
    print("Application data seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
