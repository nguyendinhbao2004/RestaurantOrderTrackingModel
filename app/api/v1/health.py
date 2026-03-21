"""
app/api/v1/health.py
---------------------
Health check endpoint — no authentication required.
Exposes readiness (models loaded) and liveness states.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.models.model_manager import model_manager

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    models_ready: bool
    service: str = "voice-ai-sidecar"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness & Readiness Check",
    description="Returns service status and whether AI models are loaded.",
)
async def health_check() -> HealthResponse:
    """
    Used by Docker HEALTHCHECK and the .NET 10 backend to verify
    that the sidecar is alive and models are ready to serve.
    """
    return HealthResponse(
        status="ok" if model_manager.is_ready else "starting",
        models_ready=model_manager.is_ready,
    )
