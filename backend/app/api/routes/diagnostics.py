"""Standalone diagnostic routes for schema validation, OpenAPI inspection, and repository scanning."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core.exceptions import APIDetectiveError
from backend.app.diagnostics.schema_validator import validate_payload_against_schema
from backend.app.schemas.diagnostics import (
    RepositoryAnalysisResult,
    SchemaValidationRequest,
    SchemaValidationResponse,
    SpecInspectRequest,
    SpecInspectResponse,
)
from backend.app.tools.openapi_parser import inspect_openapi_spec
from backend.app.tools.repository_inspector import inspect_repository

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


class RepositoryInspectPayload(BaseModel):
    repository_path: str


@router.post("/validate-schema", response_model=SchemaValidationResponse)
def validate_schema_endpoint(payload: SchemaValidationRequest) -> SchemaValidationResponse:
    """Validate a JSON payload against a JSON Schema definition."""
    findings = validate_payload_against_schema(
        payload.payload,
        payload.schema_def,
        context_label="request",
    )
    return SchemaValidationResponse(valid=len(findings) == 0, findings=findings)


@router.post("/inspect-spec", response_model=SpecInspectResponse)
def inspect_spec_endpoint(payload: SpecInspectRequest) -> SpecInspectResponse:
    """Parse and inspect an OpenAPI 3.0/3.1 or Swagger 2.0 specification."""
    return inspect_openapi_spec(payload.content)


@router.post("/inspect-repository", response_model=RepositoryAnalysisResult)
def inspect_repository_endpoint(payload: RepositoryInspectPayload) -> RepositoryAnalysisResult:
    """Scan a local repository path in read-only mode for API integrations."""
    try:
        return inspect_repository(payload.repository_path)
    except APIDetectiveError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
