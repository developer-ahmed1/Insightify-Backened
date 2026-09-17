"""
SightEngine API client for image/video scam detection.

Uses https://sightengine.com/ for:
- Scam/fraud content detection in images
- Text extraction from screenshots
- NSFW/moderation checks
- Deepfake detection for video frames

The results are mapped to the same Detection schema as Gemini text results
for a unified detection response pipeline.
"""
import hashlib
import time
from typing import Optional

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SightEngineClient:
    """
    Client for SightEngine image/video moderation API.

    API Docs: https://sightengine.com/docs/
    """

    def __init__(self):
        self.api_user = settings.sightengine_api_user
        self.api_secret = settings.sightengine_api_secret
        self.base_url = settings.sightengine_api_url

    async def analyze_image(
        self,
        image_bytes: bytes,
        filename: str = "image.jpg",
    ) -> dict:
        """
        Analyze an image for scam/fraud indicators using SightEngine.

        Args:
            image_bytes: Raw image bytes
            filename: Original filename

        Returns:
            dict matching the Detection schema shape:
            {
                "verdict": "Likely Scam" | "Suspicious" | "Likely Safe",
                "confidence_score": 0-100,
                "scam_category": "Phishing" | "Fraud" | ...,
                "red_flags": [...],
                "explanation": "...",
                "recommended_actions": [...],
                "educational_tip": "...",
                "ai_provider": "sightengine",
                "input_hash": "...",
                "processing_time_ms": ...,
                "raw_response": {...},
            }
        """
        start_time = time.time()
        input_hash = hashlib.sha256(image_bytes).hexdigest()

        if not self.api_user or not self.api_secret:
            logger.warning("SightEngine API credentials not configured, using fallback")
            return self._fallback_result(input_hash, start_time)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # SightEngine check endpoint with AI-generation, deepfake, and scam detection
                response = await client.post(
                    f"{self.base_url}/check.json",
                    data={
                        "models": "genai,deepfake,scam,text-content",
                        "api_user": self.api_user,
                        "api_secret": self.api_secret,
                    },
                    files={
                        "media": (filename, image_bytes, "image/jpeg"),
                    },
                )

                if response.status_code != 200:
                    logger.error(f"SightEngine API error: {response.status_code} {response.text}")
                    return self._fallback_result(input_hash, start_time)

                data = response.json()
                processing_time = int((time.time() - start_time) * 1000)

                return self._parse_sightengine_response(data, input_hash, processing_time)

        except Exception as e:
            logger.error(f"SightEngine analysis error: {e}")
            return self._fallback_result(input_hash, start_time)

    async def analyze_image_url(self, image_url: str) -> dict:
        """Analyze an image by URL instead of bytes."""
        start_time = time.time()
        input_hash = hashlib.sha256(image_url.encode()).hexdigest()

        if not self.api_user or not self.api_secret:
            return self._fallback_result(input_hash, start_time)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/check.json",
                    params={
                        "url": image_url,
                        "models": "genai,deepfake,scam,text-content",
                        "api_user": self.api_user,
                        "api_secret": self.api_secret,
                    },
                )

                if response.status_code != 200:
                    logger.error(f"SightEngine URL API error: {response.status_code}")
                    return self._fallback_result(input_hash, start_time)

                data = response.json()
                processing_time = int((time.time() - start_time) * 1000)
                return self._parse_sightengine_response(data, input_hash, processing_time)

        except Exception as e:
            logger.error(f"SightEngine URL analysis error: {e}")
            return self._fallback_result(input_hash, start_time)

    def _parse_sightengine_response(
        self,
        data: dict,
        input_hash: str,
        processing_time: int,
    ) -> dict:
        """
        Parse SightEngine API response into our unified detection schema.

        SightEngine models:
        - genai (type.ai_generated: 0.0-1.0): Detects AI vs Real image
        - deepfake (deepfake.prob: 0.0-1.0): Detects facial manipulation
        - scam (scam.prob: 0.0-1.0): Scammer profile matching
        - text (text.profanity, personal, link): Text extracted from image
        """
        red_flags = []
        scam_category = None
        explanation_parts = []

        # 1. AI-Generated Image Detection (genai model)
        type_data = data.get("type", {})
        ai_generated_score = 0.0
        if isinstance(type_data, dict):
            ai_generated_score = float(type_data.get("ai_generated", 0.0))

        # 2. Deepfake Detection
        deepfake_data = data.get("deepfake", {})
        deepfake_score = 0.0
        if isinstance(deepfake_data, dict):
            deepfake_score = float(deepfake_data.get("prob", 0.0))

        # 3. Scam Profile Detection
        scam_score = 0.0
        scam_data = data.get("scam", {})
        if isinstance(scam_data, dict):
            scam_score = float(scam_data.get("prob", 0.0))
        elif isinstance(scam_data, (int, float)):
            scam_score = float(scam_data)

        # Evaluate AI Generation
        if ai_generated_score >= 0.70:
            red_flags.append(f"AI-Generated Media detected ({ai_generated_score:.0%} probability)")
            explanation_parts.append(
                f"This image was identified as AI-generated ({ai_generated_score:.0%} confidence). "
                "Synthetic media is commonly used in fake profiles, romance scams, and impersonation."
            )
            scam_category = "AI Generated / Impersonation"
        elif ai_generated_score >= 0.40:
            red_flags.append(f"Possible AI-generated content ({ai_generated_score:.0%} probability)")
            explanation_parts.append(
                f"Visual patterns suggest potential AI generation ({ai_generated_score:.0%})."
            )
            scam_category = scam_category or "Suspicious Media"

        # Evaluate Deepfake
        if deepfake_score >= 0.50:
            red_flags.append(f"Deepfake / facial manipulation detected ({deepfake_score:.0%})")
            explanation_parts.append("Facial landmarks show signs of synthetic alteration or face replacement.")
            scam_category = scam_category or "Deepfake"

        # Evaluate Scam Score
        if scam_score > 0.50:
            red_flags.append("Visual elements match known scam and fraud patterns")
            explanation_parts.append(f"Scam profile confidence: {scam_score:.0%}")
            scam_category = scam_category or "Fraud"

        # Text content extracted from image
        text_data = data.get("text", {})
        if isinstance(text_data, dict):
            personal = text_data.get("personal")
            if (isinstance(personal, list) and len(personal) > 0) or (isinstance(personal, (int, float)) and personal > 0.5):
                red_flags.append("Personal information solicitation detected in image text")
                scam_category = scam_category or "Phishing"
            links = text_data.get("link")
            if (isinstance(links, list) and len(links) > 0) or (isinstance(links, (int, float)) and links > 0.5):
                red_flags.append("Suspicious external link detected in image text")
                scam_category = scam_category or "Phishing"
            profanity = text_data.get("profanity")
            if (isinstance(profanity, list) and len(profanity) > 0) or (isinstance(profanity, (int, float)) and profanity > 0.5):
                red_flags.append("Profane or deceptive wording detected in image")

        # Overall verdict & confidence calculation
        max_threat_score = max(ai_generated_score, deepfake_score, scam_score)

        if max_threat_score >= 0.70:
            verdict = "Likely Scam"
            confidence = int(max_threat_score * 100)
        elif max_threat_score >= 0.40 or len(red_flags) >= 1:
            verdict = "Suspicious"
            confidence = int(max(max_threat_score, 0.5) * 100)
        else:
            verdict = "Likely Safe"
            confidence = int((1.0 - max_threat_score) * 100)

        if not explanation_parts:
            if verdict == "Likely Safe":
                explanation_parts.append(
                    f"Authentic image: No AI generation or scam indicators detected (Real image confidence: {confidence}%)."
                )
            else:
                explanation_parts.append("The image exhibits potential digital manipulation or deception.")

        # Recommended actions
        if verdict == "Likely Scam":
            recommended_actions = [
                "Do not trust this image as evidence or identity verification",
                "Do not send money or personal credentials to this profile/sender",
                "Perform a reverse image search to find original sources",
                "Report this profile or message immediately",
            ]
        elif verdict == "Suspicious":
            recommended_actions = [
                "Verify the sender's identity through independent channels",
                "Inspect image details (hands, text, reflections, background symmetry)",
                "Avoid sharing or acting on urgent requests from this source",
            ]
        else:
            recommended_actions = [
                "Image appears genuine and authentic",
                "Always verify unexpected communications before acting",
            ]

        educational_tip = (
            "Generative AI can create convincing fake people, receipts, and documents. "
            "Always verify identity through voice calls or established official channels."
        )

        return {
            "verdict": verdict,
            "confidence_score": confidence,
            "scam_category": scam_category,
            "red_flags": red_flags,
            "explanation": " ".join(explanation_parts),
            "recommended_actions": recommended_actions,
            "educational_tip": educational_tip,
            "ai_provider": "sightengine",
            "input_hash": input_hash,
            "processing_time_ms": processing_time,
            "raw_response": data,
        }

    def _fallback_result(self, input_hash: str, start_time: float) -> dict:
        """Return a safe fallback result when API is unavailable."""
        processing_time = int((time.time() - start_time) * 1000)
        return {
            "verdict": "Suspicious",
            "confidence_score": 50,
            "scam_category": None,
            "red_flags": ["Unable to perform full image analysis"],
            "explanation": "Image analysis service is temporarily unavailable. Please try again later.",
            "recommended_actions": [
                "Try again later",
                "Exercise caution with unfamiliar images",
            ],
            "educational_tip": "Always verify image content from trusted sources.",
            "ai_provider": "sightengine_fallback",
            "input_hash": input_hash,
            "processing_time_ms": processing_time,
            "raw_response": None,
        }


# Global singleton
sightengine_client = SightEngineClient()
