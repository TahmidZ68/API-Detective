"""Application configuration management."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Centralized configuration for API Detective."""

    app_name: str = Field(default_factory=lambda: os.getenv("APP_NAME", "API Detective"))
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    app_debug: bool = Field(
        default_factory=lambda: os.getenv("APP_DEBUG", "false").lower() in ("1", "true", "yes")
    )
    api_host: str = Field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = Field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Database
    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./api_detective.db")
    )

    # Security & Network
    block_private_networks: bool = Field(
        default_factory=lambda: os.getenv("BLOCK_PRIVATE_NETWORKS", "true").lower()
        in ("1", "true", "yes")
    )
    allow_localhost_targets: bool = Field(
        default_factory=lambda: os.getenv("ALLOW_LOCALHOST_TARGETS", "false").lower()
        in ("1", "true", "yes")
    )
    max_redirects: int = Field(default_factory=lambda: int(os.getenv("MAX_REDIRECTS", "3")))
    http_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_SECONDS", "15.0"))
    )
    max_response_bytes: int = Field(
        default_factory=lambda: int(os.getenv("MAX_RESPONSE_BYTES", str(5 * 1024 * 1024)))
    )
    redact_secrets: bool = Field(
        default_factory=lambda: os.getenv("REDACT_SECRETS", "true").lower() in ("1", "true", "yes")
    )
    persist_request_bodies: bool = Field(
        default_factory=lambda: os.getenv("PERSIST_REQUEST_BODIES", "false").lower()
        in ("1", "true", "yes")
    )
    data_retention_days: int = Field(
        default_factory=lambda: int(os.getenv("DATA_RETENTION_DAYS", "30"))
    )

    # Agent settings
    agent_max_iterations: int = Field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_ITERATIONS", "6"))
    )
    agent_tool_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("AGENT_TOOL_TIMEOUT_SECONDS", "20.0"))
    )
    allow_repo_transmission_to_llm: bool = Field(
        default_factory=lambda: os.getenv("ALLOW_REPO_TRANSMISSION_TO_LLM", "false").lower()
        in ("1", "true", "yes")
    )
    require_approval_for_file_edits: bool = Field(
        default_factory=lambda: os.getenv("REQUIRE_APPROVAL_FOR_FILE_EDITS", "true").lower()
        in ("1", "true", "yes")
    )

    # Optional LLM Provider
    llm_provider: Literal["none", "openai", "gemini", "anthropic", "local"] = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "none")  # type: ignore[arg-type,return-value]
    )
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    llm_api_key: str = Field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))


_runtime_overrides: dict[str, object] = {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance with any runtime overrides applied."""
    base = Settings()
    if _runtime_overrides:
        data = base.model_dump()
        data.update(_runtime_overrides)
        return Settings(**data)
    return base


def update_runtime_settings(updates: dict[str, object]) -> Settings:
    """Update runtime settings in memory and clear cache."""
    for key, value in updates.items():
        if value is not None:
            _runtime_overrides[key] = value
    get_settings.cache_clear()
    return get_settings()


def load_yaml_config(path: Path) -> dict[str, object]:
    """Load configuration from a YAML file safely."""
    import yaml

    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        content = yaml.safe_load(f)
    return content if isinstance(content, dict) else {}
