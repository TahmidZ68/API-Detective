"""Investigation, dashboard overview, repair approval, and report export endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from backend.app.api.dependencies import get_investigation_service
from backend.app.core.exceptions import APIDetectiveError
from backend.app.schemas.diagnostics import (
    ApproveFixRequest,
    DashboardOverviewStats,
    InvestigationReport,
    InvestigationRequest,
)
from backend.app.services.investigation_service import InvestigationService
from backend.app.services.report_exporter import (
    export_report_html,
    export_report_json,
    export_report_markdown,
)

router = APIRouter(tags=["investigations"])


@router.get("/dashboard/overview", response_model=DashboardOverviewStats)
def get_dashboard_overview(
    service: InvestigationService = Depends(get_investigation_service),
) -> DashboardOverviewStats:
    """Return real backend metrics and recent activity for the dashboard overview."""
    return service.get_dashboard_overview()


@router.get("/investigations", response_model=list[InvestigationReport])
def list_investigations(
    limit: int = Query(default=50, ge=1, le=200),
    service: InvestigationService = Depends(get_investigation_service),
) -> list[InvestigationReport]:
    """List persisted diagnostic investigations."""
    return service.list_investigations(limit=limit)


@router.post("/investigations", response_model=InvestigationReport, status_code=201)
def create_investigation(
    payload: InvestigationRequest,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationReport:
    """Execute a multi-step agent investigation and persist the structured report."""
    try:
        return service.create_and_run_investigation(payload)
    except APIDetectiveError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc


@router.get("/investigations/{investigation_id}", response_model=InvestigationReport)
def get_investigation(
    investigation_id: str,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationReport:
    """Retrieve a specific investigation report by ID."""
    report = service.get_investigation(investigation_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Investigation '{investigation_id}' not found."},
        )
    return report


@router.post("/investigations/{investigation_id}/approve-fix", response_model=InvestigationReport)
def approve_investigation_fix(
    investigation_id: str,
    payload: ApproveFixRequest,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationReport:
    """Approve and optionally apply a proposed remediation fix, then run verification."""
    try:
        return service.approve_and_apply_fix(investigation_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FIX_ID", "message": str(exc)},
        ) from exc
    except APIDetectiveError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc


@router.get("/investigations/{investigation_id}/export")
def export_investigation_report(
    investigation_id: str,
    format: Literal["json", "markdown", "html"] = Query(default="json"),
    service: InvestigationService = Depends(get_investigation_service),
) -> PlainTextResponse:
    """Export an investigation report as JSON, Markdown, or standalone HTML."""
    report = service.get_investigation(investigation_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Investigation '{investigation_id}' not found."},
        )
    if format == "markdown":
        return PlainTextResponse(
            content=export_report_markdown(report),
            media_type="text/markdown; charset=utf-8",
        )
    if format == "html":
        return PlainTextResponse(
            content=export_report_html(report),
            media_type="text/html; charset=utf-8",
        )
    return PlainTextResponse(
        content=export_report_json(report),
        media_type="application/json; charset=utf-8",
    )
