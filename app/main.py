"""
Insightyfy FastAPI Application Entry Point.

JWT-based authentication (no Firebase dependency).
Aligned with BACKEND-API-SPEC.md RFC.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.database import init_db, close_db
from app.core.redis import close_redis
from app.core.middleware import setup_middleware
from app.core.logging import setup_logging, get_logger
from app.api.v1.router import api_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    logger.info("Starting Insightyfy API...")
    setup_logging()

    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Auth: JWT (google-auth for OAuth)")
    logger.info(f"AI: Gemini {settings.gemini_model} + SightEngine")

    # Initialize database tables
    try:
        await init_db()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization error: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Insightyfy API...")
    await close_db()
    await close_redis()
    logger.info("Cleanup complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="""
        Insightyfy API — AI-powered scam detection & cybersecurity companion.

        ## Features

        - **AI Scam Detection**: Analyze text, images, audio, and video for scam indicators
        - **Community Threat Feed**: Curated threat intelligence
        - **Gamification**: XP, badges, achievements, and leaderboard
        - **Quiz & Education**: Cyber-awareness learning
        - **Scam Reports**: Community threat reporting

        ## Authentication

        JWT Bearer token authentication.
        Include your access token in the Authorization header:

        ```
        Authorization: Bearer <access_token>
        ```

        Get tokens via POST /api/v1/auth/register or POST /api/v1/auth/login
        """,
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Setup middleware
    setup_middleware(app)

    # Include API routers — note: router already has /api/v1 prefix
    app.include_router(api_router)

    # ---------------------------------------------------------------------------
    # Health check endpoint — RFC §16.1
    # ---------------------------------------------------------------------------
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return JSONResponse({
            "status": "healthy",
            "service": settings.app_name,
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API info."""
        return {
            "service": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs" if settings.debug else None,
            "health": "/health",
            "api": "/api/v1",
        }

    # Quick test endpoint (dev only)
    if settings.debug:
        @app.post("/test/detect", tags=["Test"])
        async def test_detect(text: str):
            """
            Quick test endpoint for scam detection.
            Only available in debug mode, no auth required.
            """
            from app.services.detection.gemini_client import gemini_client
            result = await gemini_client.analyze_text(text)
            return {
                "input": text[:100] + "..." if len(text) > 100 else text,
                "verdict": result.get("verdict"),
                "confidence": result.get("confidence_score"),
                "category": result.get("scam_category"),
                "red_flags": result.get("red_flags", []),
                "explanation": result.get("explanation"),
                "ai_provider": result.get("ai_provider"),
            }

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
