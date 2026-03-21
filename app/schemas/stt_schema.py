"""
app/schemas/stt_schema.py
--------------------------
Pydantic v2 request/response models for the STT endpoint.
"""

from pydantic import BaseModel, Field


class STTRequest(BaseModel):
    """Optional JSON body for configuring a transcription request."""
    language: str | None = Field(
        default=None,
        description="ISO-639-1 language code (e.g. 'en', 'vi'). None = auto-detect.",
    )


class TranscribedSegment(BaseModel):
    """A single time-aligned text segment from the transcription."""
    start: float = Field(description="Segment start time in seconds.")
    end: float = Field(description="Segment end time in seconds.")
    text: str = Field(description="Transcribed text for this segment.")


class STTResponse(BaseModel):
    """Full transcription response returned to the client."""
    text: str = Field(description="Complete transcribed text (all segments joined).")
    detected_language: str = Field(description="Detected or specified language code.")
    segments: list[TranscribedSegment] = Field(
        default_factory=list,
        description="Per-segment transcription detail.",
    )
