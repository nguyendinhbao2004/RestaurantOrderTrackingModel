"""
app/api/v1/tts.py
------------------
TTS (Text-to-Speech) router using OpenAI TTS API.

Endpoint:
  POST /api/v1/tts/synthesize — JSON body → chunked WAV stream.

Authentication: X-API-Key header.
"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings

from app.schemas.tts_schema import TTSRequest, TTSResponse
from app.services.piper_service import PiperService

router = APIRouter(tags=["TTS"])

_CHUNK_SIZE = 32 * 1024  # 32 KB chunks


def _get_piper_service(settings: Settings = Depends(get_settings)) -> PiperService:
    """Dependency factory for PiperService."""
    return PiperService(settings=settings)


@router.post(
    "/tts/synthesize",
    status_code=status.HTTP_200_OK,
    summary="Synthesize Text to Speech (Cloudflare Workers AI TTS)",
    description=(
        "POST a JSON body with `text`, optional `voice` (alloy, echo, fable, onyx, nova, shimmer), and `speed`. "
        "Returns a chunked WAV stream. Uses Cloudflare Workers AI TTS for high-quality speech synthesis."
    ),
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "Chunked WAV audio stream.",
        }
    },
)
async def synthesize_speech(
    request: TTSRequest,
    service: PiperService = Depends(_get_piper_service),
) -> StreamingResponse:
    """
    Pipeline:
    1. Validate TTSRequest (text, speed).
    2. Synthesize via PiperService (thread-pool dispatched).
    3. Stream WAV bytes back in 32 KB chunks.
    """
    result: TTSResponse = await service.synthesize(
        text=request.text,
        speed=request.speed,
    )

    audio_buf = io.BytesIO(result.audio_bytes)

    async def _chunk_gen():
        while chunk := audio_buf.read(_CHUNK_SIZE):
            yield chunk

    return StreamingResponse(
        content=_chunk_gen(),
        media_type="audio/wav",
        headers={
            "Content-Length":             str(len(result.audio_bytes)),
            "X-Sample-Rate":              str(result.sample_rate),
            "X-Voice":                    result.voice,
            "X-Audio-Format":             result.format,
            "Access-Control-Expose-Headers": (
                "X-Sample-Rate,X-Voice,X-Audio-Format"
            ),
        },
    )
