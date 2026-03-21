"""
app/models/model_manager.py
----------------------------
Model manager for API-based services. No local models to load.
"""

from app.core.logging import get_logger

logger = get_logger(__name__)


class ModelManager:
    """Central registry for AI services. No models to manage."""

    def __init__(self) -> None:
        # No local models to load; service is ready immediately.
        self._is_ready: bool = True

    async def load_all(self, settings) -> None:
        """No models to load."""
        logger.info("No local models to load. Using API services.")

    async def unload_all(self) -> None:
        """No models to unload."""
        logger.info("No local models to unload.")

    @property
    def is_ready(self) -> bool:
        # Guard against partially-initialized instances and ensure checks never crash.
        return getattr(self, "_is_ready", False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def load_all(self, settings: "Settings") -> None:
        """No local models to load (legacy stub)."""
        logger.info("No local models to load. Using API services.")
        self._is_ready = True
# Module-level singleton
model_manager = ModelManager()