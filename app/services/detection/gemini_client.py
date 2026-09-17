"""
Gemini AI API client for scam detection using official Google GenAI SDK.

Uses 'gemini-flash-latest' model for optimal performance.
"""
import hashlib
import time
import json
from typing import Optional
from enum import Enum

import google.generativeai as genai

from app.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)


# Scam detection prompt template
SCAM_DETECTION_PROMPT = """You are an expert AI scam detection system. Analyze the following content and determine if it's a scam, phishing attempt, or suspicious message.

Content to analyze:
---
{content}
---

Analyze this content and respond with a JSON object containing:
1. "verdict": One of "Likely Scam", "Suspicious", or "Likely Safe"
2. "confidence_score": A number from 0-100 indicating confidence level
3. "scam_category": If suspicious/scam, categorize as one of: "Phishing", "Tech Support", "Romance", "Investment", "Lottery", "Impersonation", "Shopping", "Job", or null if safe
4. "red_flags": Array of specific warning signs found (max 5)
5. "explanation": Brief explanation of the analysis
6. "recommended_actions": Array of recommended actions for the user (max 4)
7. "educational_tip": A helpful tip about this type of scam

Respond ONLY with valid JSON, no additional text or markdown formatting.
"""


class GeminiClient:
    """Client for Google Gemini AI API using official SDK."""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model  # gemini-2.0-flash
        self._model = None
        self._configured = False

    @property
    def is_configured(self) -> bool:
        """Check if Gemini API is configured."""
        return bool(self.api_key and self.api_key not in ["", "your-gemini-api-key"])

    def _get_model(self):
        """Get or create Gemini model instance."""
        if self._model is None and self.is_configured:
            try:
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(self.model_name)
                self._configured = True
                logger.info(f"Gemini model '{self.model_name}' initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self._model = None
        return self._model

    def _generate_hash(self, content: str) -> str:
        """Generate SHA256 hash of content for caching."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def _check_cache(self, content_hash: str) -> Optional[dict]:
        """Check Redis cache for previous result."""
        try:
            redis = await get_redis()
            if redis:
                cached = await redis.get(f"detection:{content_hash}")
                if cached:
                    logger.info(f"Cache hit for hash: {content_hash[:16]}...")
                    return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
        return None

    async def _cache_result(self, content_hash: str, result: dict, ttl: int = 86400) -> None:
        """Cache result in Redis (default 24 hours)."""
        try:
            redis = await get_redis()
            if redis:
                await redis.setex(f"detection:{content_hash}", ttl, json.dumps(result))
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    async def analyze_text(self, text: str) -> dict:
        """
        Analyze text for scam indicators using Gemini.
        
        Returns normalized result dict.
        """
        content_hash = self._generate_hash(text)
        
        # Check cache
        cached = await self._check_cache(content_hash)
        if cached:
            return cached

        start_time = time.time()

        if not self.is_configured:
            logger.info("Gemini not configured, using mock analysis")
            result = self._mock_text_analysis(text)
        else:
            result = await self._call_gemini(text)

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

        # For audio, we analyze the transcript if available
        if transcript:
            if not self.is_configured:
                result = self._mock_text_analysis(transcript)
            else:
                result = await self._call_gemini(
                    f"[Audio Transcript]\n{transcript}"
                )
        else:
            result = {
                "verdict": "Likely Safe",
                "confidence_score": 50,
                "scam_category": None,
                "red_flags": [],
                "explanation": "Unable to analyze audio without transcript. Please provide a transcript for better analysis.",
                "recommended_actions": ["Provide transcript for detailed analysis"],
                "educational_tip": "Be cautious of unsolicited phone calls asking for personal information.",
                "ai_provider": "gemini" if self.is_configured else "mock",
            }

        result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        result["input_hash"] = content_hash
        
        await self._cache_result(content_hash, result)
        return result

    async def analyze_video(
        self, 
        video_url: str, 
        transcript: Optional[str] = None,
    ) -> dict:
        """Analyze video for scam indicators."""
        content_hash = self._generate_hash(video_url + (transcript or ""))
        
        cached = await self._check_cache(content_hash)
        if cached:
            return cached

        start_time = time.time()

        # For video, we analyze the transcript if available
        if transcript:
            if not self.is_configured:
                result = self._mock_text_analysis(transcript)
            else:
                result = await self._call_gemini(
                    f"[Video Transcript]\n{transcript}"
                )
        else:
            result = {
                "verdict": "Likely Safe",
                "confidence_score": 50,
                "scam_category": None,
                "red_flags": [],
                "explanation": "Unable to analyze video without transcript. Please provide a transcript for better analysis.",
                "recommended_actions": ["Provide transcript for detailed analysis"],
                "educational_tip": "Scam videos often use urgency tactics and fake testimonials.",
                "ai_provider": "gemini" if self.is_configured else "mock",
            }

        result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        result["input_hash"] = content_hash
        
        await self._cache_result(content_hash, result)
        return result

    async def _call_gemini(self, content: str) -> dict:
        """Call Gemini API for scam detection using official SDK."""
        try:
            model = self._get_model()
            if model is None:
                logger.warning("Gemini model not available, using mock")
                return self._mock_text_analysis(content)
            
            prompt = SCAM_DETECTION_PROMPT.format(content=content)
            
            # Generate content asynchronously without blocking the event loop
            import asyncio
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=1024,
                )
            )
            
            # Extract the generated text
            generated_text = response.text
            
            # Parse JSON from response
            try:
                # Clean the response - remove markdown code blocks if present
                clean_text = generated_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                
                result = json.loads(clean_text.strip())
                result["ai_provider"] = "gemini"
                result["model"] = self.model_name
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Gemini response: {e}")
                logger.debug(f"Raw response: {generated_text}")
                # Fall back to mock with the content for basic analysis
                return self._mock_text_analysis(content)
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._mock_text_analysis(content)

    # Mock responses for development
    def _mock_text_analysis(self, text: str) -> dict:
        """Generate mock analysis for text when API not configured."""
        text_lower = text.lower()
        
        # Simple keyword-based mock detection
        scam_keywords = {
            "high_risk": [
                "urgent", "suspended", "blocked", "verify your account",
                "click here immediately", "your account will be", "wire transfer",
                "bitcoin", "crypto investment", "guaranteed returns", "act now"
            ],
            "medium_risk": [
                "winner", "congratulations", "prize", "lottery", "selected",
                "offer", "free money", "inheritance", "prince", "million dollars"
            ],
            "low_risk": [
                "verify", "confirm", "update", "click", "link", "password"
            ]
        }
        
        red_flags = []
        high_count = 0
        medium_count = 0
        low_count = 0
        
        for keyword in scam_keywords["high_risk"]:
            if keyword in text_lower:
                red_flags.append(f"High-risk phrase detected: '{keyword}'")
                high_count += 1
        
        for keyword in scam_keywords["medium_risk"]:
            if keyword in text_lower:
                red_flags.append(f"Suspicious phrase: '{keyword}'")
                medium_count += 1
        
        for keyword in scam_keywords["low_risk"]:
            if keyword in text_lower:
                low_count += 1
        
        # Calculate verdict and confidence
        if high_count >= 2 or (high_count >= 1 and medium_count >= 1):
            verdict = "Likely Scam"
            confidence = min(95, 70 + high_count * 8 + medium_count * 4)
            category = self._detect_category(text_lower)
        elif high_count >= 1 or medium_count >= 2:
            verdict = "Suspicious"
            confidence = 50 + high_count * 10 + medium_count * 5
            category = self._detect_category(text_lower)
        elif medium_count >= 1 or low_count >= 2:
            verdict = "Suspicious"
            confidence = 40 + medium_count * 8 + low_count * 5
            category = "Potential Scam"
        else:
            verdict = "Likely Safe"
            confidence = 85
            category = None
        
        return {
            "verdict": verdict,
            "confidence_score": min(100, confidence),
            "scam_category": category,
            "red_flags": red_flags[:5],
            "explanation": self._generate_explanation(verdict, red_flags),
            "recommended_actions": self._get_recommended_actions(verdict),
            "educational_tip": self._get_educational_tip(category),
            "ai_provider": "mock",
            "model": "keyword-based",
        }

    def _detect_category(self, text: str) -> str:
        """Detect scam category from text."""
        categories = {
            "Phishing": ["verify", "account", "suspended", "password", "login", "bank"],
            "Tech Support": ["computer", "virus", "microsoft", "tech support", "infected"],
            "Romance": ["love", "dating", "relationship", "lonely", "partner"],
            "Investment": ["invest", "crypto", "bitcoin", "returns", "profit", "trading"],
            "Lottery": ["winner", "lottery", "prize", "congratulations", "won"],
            "Impersonation": ["irs", "government", "police", "official", "authority"],
            "Shopping": ["order", "delivery", "package", "shipping", "purchase"],
            "Job": ["job offer", "work from home", "hiring", "salary", "recruitment"],
        }
        
        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category
        
        return "Phishing"  # Default

    def _generate_explanation(self, verdict: str, red_flags: list) -> str:
        """Generate explanation based on verdict and red flags."""
        if verdict == "Likely Scam":
            return (
                f"This content shows {len(red_flags)} warning signs commonly "
                "associated with scams. Exercise extreme caution and do not "
                "interact with this content."
            )
        elif verdict == "Suspicious":
            return (
                "This content contains elements that could indicate a scam. "
                "Proceed with caution and verify the source through official channels."
            )
        return "This content appears to be legitimate based on our analysis. However, always remain vigilant."

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
            "Tech Support": "Real tech companies don't cold-call about computer problems. Microsoft will never call you.",
            "Romance": "Be wary of online relationships where the person asks for money before meeting in person.",
            "Investment": "If an investment sounds too good to be true, it probably is. Always research before investing.",
            "Lottery": "You cannot win a lottery you didn't enter. All real lotteries require you to buy a ticket.",
            "Impersonation": "Government agencies communicate through official channels, not via text messages or social media.",
            "Shopping": "Only shop on secure websites and verify unusual delivery notifications directly with the carrier.",
            "Job": "Legitimate employers never ask for money upfront for training or equipment.",
            "Potential Scam": "Always verify requests for money or personal information through official channels.",
        }
        return tips.get(category, "Trust your instincts - if something feels wrong, it probably is.")


# Singleton instance
gemini_client = GeminiClient()
