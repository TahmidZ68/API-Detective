"""Agent and security configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.config import get_settings, update_runtime_settings
from backend.app.schemas.diagnostics import AgentSettingsPayload, AgentSettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])


def _build_settings_response() -> AgentSettingsResponse:
    s = get_settings()
    return AgentSettingsResponse(
        llm_provider=s.llm_provider,
        llm_model=s.llm_model,
        llm_api_key_configured=bool(s.llm_api_key and s.llm_api_key.strip()),
        llm_base_url=s.llm_base_url,
        agent_max_iterations=s.agent_max_iterations,
        http_timeout_seconds=s.http_timeout_seconds,
        block_private_networks=s.block_private_networks,
        allow_localhost_targets=s.allow_localhost_targets,
        allow_repo_transmission_to_llm=s.allow_repo_transmission_to_llm,
        require_approval_for_file_edits=s.require_approval_for_file_edits,
        redact_secrets=s.redact_secrets,
        persist_request_bodies=s.persist_request_bodies,
    )


@router.get("", response_model=AgentSettingsResponse)
def get_agent_settings() -> AgentSettingsResponse:
    """Return current agent and security settings with secrets masked."""
    return _build_settings_response()


@router.put("", response_model=AgentSettingsResponse)
def update_agent_settings(payload: AgentSettingsPayload) -> AgentSettingsResponse:
    """Update runtime agent and security settings."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    update_runtime_settings(updates)
    return _build_settings_response()
