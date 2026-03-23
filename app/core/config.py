"""
app/core/config.py
------------------
Centralized application configuration using Pydantic-Settings v2.
All values are read from environment variables (or .env file).
"""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings.
    Field names map directly to environment variable names (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # App
    # ------------------------------------------------------------------ #
    app_env: str = Field(default="development", description="development | production")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8001)
    log_level: str = Field(default="INFO")

    # ------------------------------------------------------------------ #
    # Security
    # ------------------------------------------------------------------ #
    api_key: str = Field(
        default="changeme",
        description="Shared secret for X-API-Key header (sidecar internal auth).",
    )

    # ------------------------------------------------------------------ #
    # AI API Keys
    # ------------------------------------------------------------------ #
    cloudflare_account_id: str = Field(
        default="",
        description="Cloudflare Account ID for Workers AI.",
    )
    cloudflare_api_token: str = Field(
        default="",
        description="Cloudflare API Token for Workers AI.",
    )

    # ------------------------------------------------------------------ #
    # .NET 10 Backend API
    # ------------------------------------------------------------------ #
    dotnet_api_base_url: str = Field(
        default="http://localhost:5000",
        description="Base URL of the .NET 10 API (e.g. http://localhost:5000).",
    )
    dotnet_api_key: str = Field(
        default="changeme-dotnet",
        description="API key sent in X-API-Key header to the .NET 10 backend.",
    )
    dotnet_voice_callback_path: str = Field(
        default="/api/voicecommands/callback",
        description="Relative callback path on .NET backend to receive STT results.",
    )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns a cached singleton Settings instance."""
    return Settings()
