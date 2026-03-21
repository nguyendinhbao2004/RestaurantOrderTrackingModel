"""
app/services/whisper_service.py
--------------------------------
Business logic layer for Speech-to-Text using Cloudflare Workers AI Whisper.

All public methods are async.
"""

from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.stt_schema import STTResponse, TranscribedSegment

logger = get_logger(__name__)


class WhisperService:
    """
    Async wrapper around Cloudflare Workers AI Whisper transcription.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._account_id = settings.cloudflare_account_id
        self._api_token = settings.cloudflare_api_token
        self._base_url = f"https://api.cloudflare.com/client/v4/accounts/{self._account_id}/ai/run"

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        beam_size: Optional[int] = None,  # Not used in API
    ) -> STTResponse:
        """
        Transcribe audio bytes to text using Cloudflare Workers AI Whisper.

        Args:
            audio_data: Raw audio bytes (WAV / MP3 / OGG / FLAC).
            language:   ISO-639-1 code hint, or None for auto-detection.
            beam_size:  Ignored for API.

        Returns:
            STTResponse with full text and basic segments.

        Raises:
            Exception: propagates API errors.
        """
        logger.info(
            "Starting STT transcription via Cloudflare Workers AI.",
            language=language or "auto",
            audio_bytes=len(audio_data),
        )

        try:
            payload: dict[str, object] = {
                # Cloudflare Whisper expects an array of unsigned 8-bit integers.
                "audio": list(audio_data),
            }
            if language:
                payload["language"] = language

            headers = {
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/@cf/openai/whisper",
                    json=payload,
                    headers=headers,
                    timeout=90.0,
                )
                response.raise_for_status()
                raw = response.json()

            # Cloudflare REST returns data under "result".
            # Keep fallback for older/plain payloads to be resilient.
            result = raw.get("result", raw)

            text = str(result.get("text", "")).strip()

            words = result.get("words") or []
            segments: list[TranscribedSegment] = []
            for word in words:
                word_text = str(word.get("word", "")).strip()
                if not word_text:
                    continue
                segments.append(
                    TranscribedSegment(
                        start=float(word.get("start", 0.0)),
                        end=float(word.get("end", 0.0)),
                        text=word_text,
                    )
                )

            if not segments:
                segments = [TranscribedSegment(start=0.0, end=0.0, text=text)]

            stt_response = STTResponse(
                text=text,
                detected_language=language or "auto",
                segments=segments,
            )

            logger.info(
                "STT transcription complete.",
                text_length=len(text),
            )
            return stt_response

        except Exception as exc:
            logger.error("STT transcription failed.", error=str(exc))
            raise


