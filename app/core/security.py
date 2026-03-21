"""
app/core/security.py
--------------------
FastAPI security dependency: X-API-Key header validation.
Inject via `Depends(verify_api_key)` on any protected route.
"""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.core.config import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def verify_api_key(
    api_key: str = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Validates the X-API-Key header against the configured secret.

    Raises:
        HTTPException 403: if the key is missing or does not match.

    Returns:
        The validated API key string.
    """
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key.",
        )
    return api_key
