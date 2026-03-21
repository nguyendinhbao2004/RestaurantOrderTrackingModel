"""
app/main.py
------------
FastAPI application entry point.

Routers:  health, stt, tts, voice (new — full command pipeline).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health, stt, tts, voice
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Voice AI Sidecar",
        description=(
            "Async STT (Cloudflare Workers AI Whisper) + TTS (Cloudflare Workers AI TTS) + "
            "Voice Command pipeline for a .NET 10 backend. "
            "Speak Vietnamese → intent is parsed → .NET API is called."
        ),
        version="2.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    API_PREFIX = "/api/v1"
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(stt.router,    prefix=API_PREFIX)
    app.include_router(tts.router,    prefix=API_PREFIX)
    app.include_router(voice.router,  prefix=API_PREFIX)   # Voice command pipeline

    return app


app = create_app()
# trigger reload
