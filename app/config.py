"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Insightyfy"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # JWT Authentication
    jwt_secret_key: str = "insightify-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60  # 1 hour
    jwt_refresh_token_expire_days: int = 30  # 30 days

    # Google OAuth (direct Google API verification, no Firebase)
    google_client_id: str = ""
    google_client_secret: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:root@localhost:5432/insightyfy"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key: str = ""
    r2_secret_key: str = ""
    r2_bucket: str = "insightyfy-media"
    r2_endpoint: str = ""
    r2_public_url: str = ""

    # Gemini API (Primary AI for text/email scam detection)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # SightEngine API (Image/Video moderation & detection)
    sightengine_api_user: str = ""
    sightengine_api_secret: str = ""
    sightengine_api_url: str = "https://api.sightengine.com/1.0"

    # Hive API (Legacy fallback)
    hive_api_key: str = ""
    hive_api_url: str = "https://api.thehiveai.com/api/v2"

    # Rate Limits - Free tier (per day)
    free_text_detections_daily: int = 10
    free_audio_detections_daily: int = 3
    free_video_detections_daily: int = 0
    free_posts_daily: int = 3

    # Rate Limits - Premium tier (per day)
    premium_text_detections_daily: int = 100
    premium_audio_detections_daily: int = 50
    premium_video_detections_daily: int = 20
    premium_posts_daily: int = 20

    # CORS
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Firebase (kept optional for legacy, not used for auth)
    firebase_credentials_path: str = "./firebase-credentials.json"
    firebase_project_id: str = ""

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def format_database_url(cls, v):
        if not v or not isinstance(v, str):
            return v
        url = v.strip()
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=require" in url:
            url = url.replace("sslmode=require", "ssl=require")
        if "channel_binding=" in url:
            parts = url.split("?")
            base = parts[0]
            params = [p for p in parts[1].split("&") if not p.startswith("channel_binding")]
            url = base + ("?" + "&".join(params) if params else "")
        return url

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
