"""
app/api/v1/stt.py
------------------
STT (Speech-to-Text) router.

Endpoints:
  POST /api/v1/stt/transcribe   — Upload audio file, returns JSON.
  POST /api/v1/stt/stream       — Upload audio file, streams JSON
                                   segments as newline-delimited JSON (NDJSON).

Authentication: X-API-Key header (enforced by verify_api_key dependency).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.config import Settings, get_settings

from app.schemas.stt_schema import STTRequest, STTResponse
from app.services.whisper_service import WhisperService

router = APIRouter(tags=["STT"])


def _get_whisper_service(settings: Settings = Depends(get_settings)) -> WhisperService:
    """Dependency factory for WhisperService."""
    return WhisperService(settings=settings)


# ---------------------------------------------------------------------------
# POST /stt/transcribe  — Full transcription, returns structured JSON
# ---------------------------------------------------------------------------

@router.post(
    "/stt/transcribe",
    response_model=STTResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe Audio to Text",
    description=(
        "Upload an audio file (WAV, MP3, OGG, FLAC) and receive a JSON "
        "response containing the full transcription text and per-segment "
        "timestamps. Integrates with Cloudflare Workers AI Whisper."
    ),
)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe (WAV/MP3/OGG/FLAC)."),
    language: str | None = Form(
        default=None,
        description="ISO-639-1 language hint (e.g. 'en', 'vi'). Leave empty for auto-detect.",
    ),
    service: WhisperService = Depends(_get_whisper_service),
) -> STTResponse:
    """
    Pipeline:
    1. Read uploaded audio bytes from the multipart form.
    2. Dispatch to WhisperService (async, thread-pool, non-blocking).
    3. Return STTResponse JSON.
    """
    audio_bytes = await file.read()
    return await service.transcribe(
        audio_data=audio_bytes,
        language=language,
    )


# ---------------------------------------------------------------------------
# POST /stt/stream  — Streaming variant: emits NDJSON segments as they arrive
# ---------------------------------------------------------------------------

@router.post(
    "/stt/stream",
    status_code=status.HTTP_200_OK,
    summary="Stream Transcription Segments (NDJSON)",
    description=(
        "Upload an audio file and receive per-segment transcription results "
        "streamed as newline-delimited JSON. Each line is a "
        "TranscribedSegment JSON object. Useful for real-time display in the "
        ".NET 10 client via Server-Sent Events or plain HTTP streaming."
    ),
    responses={
        200: {
            "content": {"application/x-ndjson": {}},
            "description": "NDJSON stream of TranscribedSegment objects.",
        }
    },
)
async def stream_transcription(
    file: UploadFile = File(..., description="Audio file to transcribe."),
    language: str | None = Form(default=None),
    service: WhisperService = Depends(_get_whisper_service),
) -> StreamingResponse:
    """
    Runs the same inference as /stt/transcribe but streams each segment
    as a JSON line the moment it is built, enabling incremental display.
    """
    audio_bytes = await file.read()
    result: STTResponse = await service.transcribe(
        audio_data=audio_bytes,
        language=language,
    )

    async def _generate():
        for seg in result.segments:
            yield json.dumps(seg.model_dump(), ensure_ascii=False) + "\n"
        # Final line: summary envelope
        yield json.dumps({
            "event": "done",
            "text": result.text,
            "detected_language": result.detected_language,
        }, ensure_ascii=False) + "\n"

    return StreamingResponse(
        content=_generate(),
        media_type="application/x-ndjson",
    )
