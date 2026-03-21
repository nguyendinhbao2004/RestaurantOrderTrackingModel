"""
app/api/v1/voice.py
--------------------
Voice command pipeline router.

Endpoints:
  POST /api/v1/voice/command
      Full pipeline: audio → STT (vi) → Intent → .NET API call → JSON result.

  POST /api/v1/voice/command/tts
      Same pipeline + TTS: synthesizes the result message as Vietnamese WAV.

Authentication: X-API-Key header.
"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

from app.schemas.voice_schema import TextCommandRequest, VoiceCommandResponse
from app.services.action_service import ActionService
from app.services.intent_service import intent_service
from app.services.piper_service import PiperService
from app.services.whisper_service import WhisperService

router = APIRouter(tags=["Voice Command"])
logger = get_logger(__name__)

_CHUNK_SIZE = 32 * 1024  # 32 KB WAV stream chunks


# ---------------------------------------------------------------------------
# Dependency factories
# ---------------------------------------------------------------------------

def _whisper(settings: Settings = Depends(get_settings)) -> WhisperService:
    return WhisperService(settings=settings)

def _piper(settings: Settings = Depends(get_settings)) -> PiperService:
    return PiperService(settings=settings)

def _action(settings: Settings = Depends(get_settings)) -> ActionService:
    return ActionService(settings=settings)


# ---------------------------------------------------------------------------
# POST /voice/command — JSON response
# ---------------------------------------------------------------------------

@router.post(
    "/voice/command",
    response_model=VoiceCommandResponse,
    status_code=status.HTTP_200_OK,
    summary="Voice Command → JSON",
    description=(
        "Upload a Vietnamese audio file. The pipeline will: "
        "(1) Transcribe with Whisper, "
        "(2) Parse intent from the transcript, "
        "(3) Execute the matching .NET 10 API call, "
        "(4) Return a structured JSON result."
    ),
)
async def voice_command(
    file: UploadFile = File(..., description="Audio file (WAV/MP3/OGG). Admin speaks Vietnamese."),
    language: str = Form(default="vi", description="STT language hint. Default: 'vi' (Vietnamese)."),
    stt: WhisperService = Depends(_whisper),
    action: ActionService = Depends(_action),
) -> VoiceCommandResponse:
    """
    Full voice command pipeline → JSON.

    Pipeline:
    1. STT  — Whisper transcribes Vietnamese audio to text.
    2. NLU  — IntentService extracts intent + params (offline, regex).
    3. API  — ActionService calls the right .NET 10 endpoint.
    4. JSON — Returns VoiceCommandResponse.
    """
    audio_bytes = await file.read()

    # ── Step 1: STT ────────────────────────────────────────────────────
    stt_result = await stt.transcribe(audio_data=audio_bytes, language=language)
    transcript = stt_result.text
    logger.info("STT complete.", transcript=transcript[:80])

    # ── Step 2: NLU ────────────────────────────────────────────────────
    parsed = intent_service.parse(transcript)
    logger.info("Intent parsed.", intent=parsed.intent, params=parsed.params)

    # ── Step 3: .NET API call ─────────────────────────────────────────
    action_result = await action.execute(intent=parsed.intent, params=parsed.params)
    logger.info(
        "Action executed.",
        intent=parsed.intent,
        success=action_result.success,
        http_status=action_result.http_status,
    )

    return VoiceCommandResponse(
        transcript=transcript,
        intent=parsed.intent,
        params=parsed.params,
        success=action_result.success,
        message=action_result.message,
        data=action_result.data,
    )


@router.post(
    "/voice/text-command",
    response_model=VoiceCommandResponse,
    status_code=status.HTTP_200_OK,
    summary="Text Command -> JSON",
    description=(
        "Accept a transcript text, parse intent and parameters, then execute the "
        "matching .NET 10 API call. Useful when STT is done client-side and only "
        "NLU + action execution is needed."
    ),
)
async def voice_text_command(
    body: TextCommandRequest,
    action: ActionService = Depends(_action),
) -> VoiceCommandResponse:
    """Text -> intent -> .NET action pipeline."""
    transcript = body.text.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Text transcript cannot be empty.")

    parsed = intent_service.parse(transcript)
    action_result = await action.execute(intent=parsed.intent, params=parsed.params)

    return VoiceCommandResponse(
        transcript=transcript,
        intent=parsed.intent,
        params=parsed.params,
        success=action_result.success,
        message=action_result.message,
        data=action_result.data,
    )


# ---------------------------------------------------------------------------
# POST /voice/command/tts — WAV audio response with result spoken aloud
# ---------------------------------------------------------------------------

@router.post(
    "/voice/command/tts",
    status_code=status.HTTP_200_OK,
    summary="Voice Command → WAV (spoken reply)",
    description=(
        "Same as /voice/command but the result message is synthesized as "
        "Vietnamese speech and returned as a chunked WAV audio stream. "
        "Useful for kiosk / hands-free scenarios where the system confirms "
        "the action out loud."
    ),
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "WAV audio stream of the spoken result message.",
        }
    },
)
async def voice_command_tts(
    file: UploadFile = File(..., description="Audio file (WAV/MP3/OGG)."),
    language: str = Form(default="vi"),
    stt: WhisperService = Depends(_whisper),
    tts: PiperService = Depends(_piper),
    action: ActionService = Depends(_action),
) -> StreamingResponse:
    """
    Full pipeline that ends with a spoken Vietnamese response.

    Extra response headers:
      X-Transcript      — STT output
      X-Intent          — Matched intent
      X-Success         — "true" | "false"
      X-Message         — Vietnamese result message (also spoken)
    """
    audio_bytes = await file.read()

    # STT
    stt_result = await stt.transcribe(audio_data=audio_bytes, language=language)
    transcript = stt_result.text

    # NLU
    parsed = intent_service.parse(transcript)

    # .NET API
    action_result = await action.execute(intent=parsed.intent, params=parsed.params)

    # TTS — speak the result message in Vietnamese
    tts_result = await tts.synthesize(text=action_result.message)

    async def _chunk_gen():
        buf = io.BytesIO(tts_result.audio_bytes)
        while chunk := buf.read(_CHUNK_SIZE):
            yield chunk

    return StreamingResponse(
        content=_chunk_gen(),
        media_type="audio/wav",
        headers={
            "Content-Length":             str(len(tts_result.audio_bytes)),
            "X-Sample-Rate":              str(tts_result.sample_rate),
            "X-Transcript":               transcript[:200],
            "X-Intent":                   parsed.intent,
            "X-Success":                  str(action_result.success).lower(),
            "X-Message":                  action_result.message[:200],
            "Access-Control-Expose-Headers": (
                "X-Sample-Rate,X-Transcript,X-Intent,X-Success,X-Message"
            ),
        },
    )
