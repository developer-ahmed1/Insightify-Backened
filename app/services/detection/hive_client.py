"""
Hive AI API client for scam detection.

This client handles communication with the Hive API for text, audio, and video
moderation. It includes mock responses when no API key is configured.
"""
import hashlib
import time
from typing import Any, Optional
from enum import Enum

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.core.exceptions import AIServiceError
from app.core.redis import get_redis

logger = get_logger(__name__)


class ContentType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"


class HiveClient:
    """Client for Hive AI moderation API."""

    # Hive API endpoints
    ENDPOINTS = {
        ContentType.TEXT: "/text/text_moderation",
        ContentType.AUDIO: "/audio/audio_moderation",
        ContentType.VIDEO: "/video/video_moderation",
    }

    def __init__(self):
        self.api_key = settings.hive_api_key
        self.base_url = settings.hive_api_url
        self.timeout = 30.0
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if Hive API is configured."""
        return bool(self.api_key and self.api_key != "your-hive-api-key")

    async def get_client(self) -> httpx.AsyncClient:
        """Get HTTP client instance."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _generate_hash(self, content: str) -> str:
        """Generate SHA256 hash of content for caching."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def _check_cache(self, content_hash: str) -> Optional[dict]:
        """Check Redis cache for previous result."""
        redis = await get_redis()
        cached = await redis.get(f"detection:{content_hash}")
        if cached:
            import json
            logger.info(f"Cache hit for hash: {content_hash[:16]}...")
            return json.loads(cached)
        return None

    async def _cache_result(self, content_hash: str, result: dict, ttl: int = 86400) -> None:
        """Cache result in Redis (default 24 hours)."""
        import json
        redis = await get_redis()
        await redis.setex(f"detection:{content_hash}", ttl, json.dumps(result))

    async def analyze_text(self, text: str) -> dict:
        """
        Analyze text for scam indicators.
        
        Returns normalized result dict.
        """
        content_hash = self._generate_hash(text)
        
        # Check cache
        cached = await self._check_cache(content_hash)
        if cached:
            return cached

        start_time = time.time()

        if not self.is_configured:
            result = self._mock_text_analysis(text)
        else:
            result = await self._call_hive_text(text)

        result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        result["input_hash"] = content_hash

        # Cache result
        await self._cache_result(content_hash, result)
        
        return result

    async def analyze_audio(self, audio_url: str, transcript: Optional[str] = None) -> dict:
        """Analyze audio for scam indicators."""
        content_hash = self._generate_hash(audio_url + (transcript or ""))
        
        cached = await self._check_cache(content_hash)
        if cached:
            return cached

        start_time = time.time()

        if not self.is_configured:
            result = self._mock_audio_analysis(transcript or "")
        else:
            result = await self._call_hive_audio(audio_url)

        result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        result["input_hash"] = content_hash
        
        await self._cache_result(content_hash, result)
        return result

    async def analyze_video(
        self, 
        video_url: str, 
        transcript: Optional[str] = None,
    ) -> dict:
        """Analyze video for scam indicators (with frame sampling)."""
        content_hash = self._generate_hash(video_url + (transcript or ""))
        
        cached = await self._check_cache(content_hash)
        if cached:
            return cached

        start_time = time.time()

        if not self.is_configured:
            result = self._mock_video_analysis(transcript or "")
        else:
            result = await self._call_hive_video(video_url)

        result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        result["input_hash"] = content_hash
        
        await self._cache_result(content_hash, result)
        return result

    # Hive API calls
    async def _call_hive_text(self, text: str) -> dict:
        """Call Hive text moderation API."""
        try:
            client = await self.get_client()
            response = await client.post(
                self.ENDPOINTS[ContentType.TEXT],
                json={"text_data": text}
            )
            response.raise_for_status()
            
            data = response.json()
            return self._normalize_hive_response(data, ContentType.TEXT)
            
        except httpx.HTTPError as e:
            logger.error(f"Hive API error: {e}")
            raise AIServiceError(f"Text analysis failed: {str(e)}")

    async def _call_hive_audio(self, audio_url: str) -> dict:
        """Call Hive audio moderation API."""
        try:
            client = await self.get_client()
            response = await client.post(
                self.ENDPOINTS[ContentType.AUDIO],
                json={"url": audio_url}
            )
            response.raise_for_status()
            
            data = response.json()
            return self._normalize_hive_response(data, ContentType.AUDIO)
            
        except httpx.HTTPError as e:
            logger.error(f"Hive API error: {e}")
            raise AIServiceError(f"Audio analysis failed: {str(e)}")

    async def _call_hive_video(self, video_url: str) -> dict:
        """Call Hive video moderation API."""
        try:
            client = await self.get_client()
            response = await client.post(
                self.ENDPOINTS[ContentType.VIDEO],
                json={"url": video_url}
            )
            response.raise_for_status()
            
            data = response.json()
            return self._normalize_hive_response(data, ContentType.VIDEO)
            
        except httpx.HTTPError as e:
            logger.error(f"Hive API error: {e}")
            raise AIServiceError(f"Video analysis failed: {str(e)}")

    def _normalize_hive_response(self, data: dict, content_type: ContentType) -> dict:
        """Normalize Hive API response to our standard format."""
        # This would parse the actual Hive response format
        # For now, return a standard structure
        # TODO: Implement actual Hive response parsing when API key is available
        
        return {
            "verdict": "Likely Safe",
            "confidence_score": 75,
            "scam_category": None,
            "red_flags": [],
            "explanation": "Analysis completed by Hive AI",
            "recommended_actions": [],
            "educational_tip": "Always verify the source before sharing personal information.",
            "raw_response": data,
            "ai_provider": "hive",
        }

    # Mock responses for development
    def _mock_text_analysis(self, text: str) -> dict:
        """Generate mock analysis for text when API not configured."""
        text_lower = text.lower()
        
        # Simple keyword-based mock detection
        scam_keywords = [
            "urgent", "act now", "limited time", "winner", "congratulations",
            "click here", "verify your account", "suspended", "password",
            "bank account", "wire transfer", "prince", "inheritance",
            "lottery", "million dollars", "free money", "investment opportunity"
        ]
        
        red_flags = []
        for keyword in scam_keywords:
            if keyword in text_lower:
                red_flags.append(f"Contains suspicious phrase: '{keyword}'")
        
        # Calculate mock confidence based on red flags
        if len(red_flags) >= 3:
            verdict = "Likely Scam"
            confidence = min(95, 70 + len(red_flags) * 5)
            category = "Phishing"
        elif len(red_flags) >= 1:
            verdict = "Suspicious"
            confidence = 50 + len(red_flags) * 10
            category = "Potential Scam"
        else:
            verdict = "Likely Safe"
            confidence = 80
            category = None
        
        return {
            "verdict": verdict,
            "confidence_score": confidence,
            "scam_category": category,
            "red_flags": red_flags[:5],  # Limit to 5
            "explanation": self._generate_explanation(verdict, red_flags),
            "recommended_actions": self._get_recommended_actions(verdict),
            "educational_tip": self._get_educational_tip(category),
            "raw_response": {"mock": True},
            "ai_provider": "mock",
        }

    def _mock_audio_analysis(self, transcript: str) -> dict:
        """Generate mock analysis for audio."""
        # Use text analysis on transcript if available
        if transcript:
            result = self._mock_text_analysis(transcript)
            result["detection_type"] = "audio"
            return result
        
        return {
            "verdict": "Likely Safe",
            "confidence_score": 70,
            "scam_category": None,
            "red_flags": [],
            "explanation": "Audio analysis completed. No transcript available for detailed analysis.",
            "recommended_actions": ["Review the audio content carefully"],
            "educational_tip": "Be cautious of unsolicited phone calls asking for personal information.",
            "raw_response": {"mock": True},
            "ai_provider": "mock",
        }

    def _mock_video_analysis(self, transcript: str) -> dict:
        """Generate mock analysis for video."""
        if transcript:
            result = self._mock_text_analysis(transcript)
            result["detection_type"] = "video"
            return result
        
        return {
            "verdict": "Likely Safe",
            "confidence_score": 65,
            "scam_category": None,
            "red_flags": [],
            "explanation": "Video analysis completed. Content appears to be safe.",
            "recommended_actions": ["Verify the source of the video"],
            "educational_tip": "Scam videos often use urgency tactics and fake testimonials.",
            "raw_response": {"mock": True},
            "ai_provider": "mock",
        }

    def _generate_explanation(self, verdict: str, red_flags: list) -> str:
        """Generate explanation based on verdict and red flags."""
        if verdict == "Likely Scam":
            return (
                f"This content shows {len(red_flags)} warning signs commonly "
                "associated with scams. Exercise extreme caution."
            )
        elif verdict == "Suspicious":
            return (
                "This content contains some elements that could indicate a scam. "
                "Proceed with caution and verify the source."
            )
        return "This content appears to be legitimate based on our analysis."

    def _get_recommended_actions(self, verdict: str) -> list:
        """Get recommended actions based on verdict."""
        if verdict == "Likely Scam":
            return [
                "Do not click any links or download attachments",
                "Do not reply or provide any personal information",
                "Block the sender/caller",
                "Report this to relevant authorities",
            ]
        elif verdict == "Suspicious":
            return [
                "Verify the sender's identity through official channels",
                "Do not share personal or financial information",
                "Research the organization independently",
            ]
        return ["Stay vigilant and verify sources when in doubt"]

    def _get_educational_tip(self, category: Optional[str]) -> str:
        """Get educational tip based on scam category."""
        tips = {
            "Phishing": "Legitimate organizations never ask for passwords or sensitive data via email or text.",
            "Tech Support": "Real tech companies don't cold-call about computer problems.",
            "Romance": "Be wary of online relationships where the person asks for money before meeting.",
            "Investment": "If an investment sounds too good to be true, it probably is.",
            "Potential Scam": "Always verify requests for money or personal information through official channels.",
        }
        return tips.get(category, "Trust your instincts - if something feels wrong, it probably is.")


# Singleton instance
hive_client = HiveClient()
