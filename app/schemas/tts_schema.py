"""
app/schemas/tts_schema.py
--------------------------
Pydantic v2 request/response models for the TTS endpoint.
"""

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """JSON body for a speech synthesis request."""
    text: str = Field(
        min_length=1,
        max_length=4000,
        description="The text to synthesize into speech.",
    )
    voice: str | None = Field(
        default="alloy",
        description="OpenAI voice: alloy, echo, fable, onyx, nova, shimmer.",
    )
    speed: float = Field(
        default=1.0,
        ge=0.25,
        le=4.0,
        description="Speech speed multiplier. 1.0 = normal rate.",
    )


class TTSResponse(BaseModel):
    """
    Internal domain model carrying synthesis output.
    The actual HTTP response is a StreamingResponse of audio bytes.
    This schema is used internally between service and route layers.
    """
    audio_bytes: bytes = Field(description="Raw audio content (WAV format).")
    sample_rate: int = Field(description="Audio sample rate in Hz.")
    voice: str | None = Field(default=None, description="Voice ID used for synthesis.")
    format: str = Field(default="wav", description="Audio container format.")
