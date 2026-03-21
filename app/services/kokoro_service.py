"""
app/services/kokoro_service.py
-------------------------------
Text-to-Speech service using Cloudflare Workers AI TTS (alternative to Piper).
"""

from __future__ import annotations

import io
from typing import Optional

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.tts_schema import TTSResponse

logger = get_logger(__name__)


class KokoroService:
    """
    Async wrapper around Cloudflare Workers AI TTS synthesis (alternative implementation).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._account_id = settings.cloudflare_account_id
        self._api_token = settings.cloudflare_api_token
        self._base_url = f"https://api.cloudflare.com/client/v4/accounts/{self._account_id}/ai/run"

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = "nova",  # Different default voice
        speed: float = 1.0,
    ) -> TTSResponse:
        """
        Synthesize speech from text using Cloudflare Workers AI TTS.

        Args:
            text:   Input text.
            voice:  Voice (alloy, echo, fable, onyx, nova, shimmer).
            speed:  Speed multiplier (0.25 to 4.0).

        Returns:
            TTSResponse with audio bytes.
        """
        logger.info("Starting TTS synthesis via Cloudflare Workers AI (Kokoro alternative).", text_length=len(text), voice=voice, speed=speed)

        async with httpx.AsyncClient() as client:
            data = {
                "text": text,
                "voice": voice or "nova",
                "speed": speed,
            }
            headers = {"Authorization": f"Bearer {self._api_token}"}

            response = await client.post(
                f"{self._base_url}/@cf/openai/tts-1",
                json=data,
                headers=headers,
                timeout=60.0,
            )
            response.raise_for_status()

            audio_bytes = response.content

        # Assume 24kHz sample rate for TTS-1
        tts_response = TTSResponse(
            audio_bytes=audio_bytes,
            sample_rate=24000,
        )

        logger.info(
            "TTS synthesis complete.",
            audio_bytes=len(audio_bytes),
            sample_rate=24000,


