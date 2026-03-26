"""
app/schemas/voice_schema.py
----------------------------
Pydantic v2 schemas for the end-to-end voice command pipeline.

Flow: Audio → STT → Intent → .NET Action → VoiceCommandResponse
"""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class ParsedIntent(BaseModel):
    """Structured result from the IntentService."""
    intent: str = Field(description="Intent name (e.g. 'create_user', 'unknown').")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted named parameters for this intent.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Match confidence [0–1]. Rule-based always returns 1.0 on match.",
    )


class ActionResult(BaseModel):
    """Result returned after calling the .NET 10 API."""
    success: bool = Field(description="True if the API call returned 2xx.")
    http_status: int = Field(description="HTTP status code from .NET API.")
    message: str = Field(description="Human-readable result message (Vietnamese).")
    data: dict[str, Any] | None = Field(
        default=None,
        description="Parsed JSON payload from the .NET API response.",
    )


class VoiceCommandResponse(BaseModel):
    """Full pipeline response returned to the .NET 10 client."""
    transcript: str = Field(description="Vietnamese text produced by Whisper STT.")
    intent: str = Field(description="Parsed intent name.")
    params: dict[str, Any] = Field(description="Extracted intent parameters.")
    success: bool = Field(description="True if the entire pipeline succeeded.")
    message: str = Field(description="Human-readable Vietnamese result message.")
    data: dict[str, Any] | None = Field(
        default=None,
        description=".NET API response payload (only on success).",
    )


class TextCommandRequest(BaseModel):
    """Request model for text-only command processing."""
    text: str = Field(
        min_length=1,
        description="Transcript text to parse and execute.",
    )
    order_id: str | None = Field(
        default=None,
        alias="orderId",
        description="Optional order ID used when adding items into an existing order.",
    )
    order_channel: str | None = Field(
        default=None,
        alias="orderChannel",
        description="Optional order channel. If omitted, sidecar defaults to 'voice'.",
    )
    audio_url: str | None = Field(
        default=None,
        alias="audioUrl",
        description="Optional audio URL for tracing source audio.",
    )
    confidence_score: float | None = Field(
        default=None,
        alias="confidenceScore",
        ge=0.0,
        le=1.0,
        description="Optional STT confidence score.",
    )


class VoiceCallbackPayload(BaseModel):
    """Payload sent from sidecar to .NET callback endpoint."""
    order_id: str = Field(alias="orderId")
    audio_url: str = Field(alias="audioUrl")
    transcribed_text: str = Field(alias="transcribedText")
    confidence_score: float = Field(alias="confidenceScore", ge=0.0, le=1.0)
    error_message: str | None = Field(default=None, alias="errorMessage")
