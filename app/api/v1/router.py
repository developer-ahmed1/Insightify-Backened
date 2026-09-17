"""
API v1 router — aggregates all feature routers.

Route paths aligned with BACKEND-API-SPEC.md RFC §18 Master Endpoint Matrix.
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.detect import router as detect_router
from app.api.v1.feed_v2 import router as feed_router
from app.api.v1.reports import router as reports_router
from app.api.v1.quiz import router as quiz_router
from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.achievements import router as achievements_router
from app.api.v1.guardians import router as guardians_router
from app.api.v1.learn import router as learn_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.admin import router as admin_router

api_router = APIRouter(prefix="/api/v1")

# RFC §2 — Authentication
api_router.include_router(auth_router)

# RFC §3-5 — Users, Profile, Settings, Activity
api_router.include_router(users_router)

# RFC §9-10 — Detection & Scan History
api_router.include_router(detect_router)

# RFC §6-7 — Threat Feed
api_router.include_router(feed_router)

# RFC §8 — Scam Reports
api_router.include_router(reports_router)

# RFC §11 — Quiz & Education
api_router.include_router(quiz_router)

# RFC §12 — Leaderboard
api_router.include_router(leaderboard_router)

# RFC §13 — Achievements
api_router.include_router(achievements_router)

# RFC §14 — Guardians (Public Profiles)
api_router.include_router(guardians_router)

# RFC §5.4 — Learn / Daily Tips
api_router.include_router(learn_router)

# RFC §15 — Notifications
api_router.include_router(notifications_router)

# Admin Panel APIs
api_router.include_router(admin_router)
