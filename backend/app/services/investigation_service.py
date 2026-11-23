"""Service layer managing investigations, database persistence, and dashboard analytics."""

from __future__ import annotations

import json
import time

import httpx
from sqlalchemy.orm import Session

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.models.investigation import InvestigationRecord
from backend.app.schemas.diagnostics import (
    ApproveFixRequest,
    DashboardOverviewStats,
    InvestigationReport,
    InvestigationRequest,
    InvestigationStepRecord,
)

SEVERITY_PRIORITY = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
}


class InvestigationService:
    """Coordinates the AgentOrchestrator and SQLAlchemy persistence layer."""

    def __init__(
        self,
        db: Session,
        *,
        http_transport: httpx.BaseTransport | None = None,
    ):
        self.db = db
        self.orchestrator = AgentOrchestrator(http_transport=http_transport)

    def create_and_run_investigation(
        self,
        request: InvestigationRequest,
    ) -> InvestigationReport:
        """Run a multi-step agent investigation and persist the redacted report."""
        report = self.orchestrator.run_investigation(request)
        self._save_report(report, request)
        return report

    def _save_report(
        self,
        report: InvestigationReport,
        request: InvestigationRequest | None = None,
    ) -> InvestigationRecord:
        highest = "informational"
        if report.findings:
            sorted_sevs = sorted(
                (f.severity for f in report.findings),
                key=lambda s: SEVERITY_PRIORITY.get(s, 5),
            )
            highest = sorted_sevs[0]

        payload_dict = report.model_dump()
        if request is not None:
            # Store sanitized request metadata for subsequent repair verification
            payload_dict["_request_context"] = {
                "url": report.target_url,
                "method": request.method,
                "repository_path": request.repository_path,
                "expected_status": request.expected_status,
            }

        existing = (
            self.db.query(InvestigationRecord)
            .filter(InvestigationRecord.investigation_id == report.investigation_id)
            .first()
        )
        if existing:
            existing.title = report.title
            existing.status = report.status
            existing.target_url = report.target_url
            existing.http_method = report.http_method
            existing.findings_count = len(report.findings)
            existing.highest_severity = highest
            existing.report_json = json.dumps(payload_dict)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        record = InvestigationRecord(
            investigation_id=report.investigation_id,
            title=report.title,
            status=report.status,
            target_url=report.target_url,
            http_method=report.http_method,
            findings_count=len(report.findings),
            highest_severity=highest,
            report_json=json.dumps(payload_dict),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_investigation(self, investigation_id: str) -> InvestigationReport | None:
        """Retrieve a single persisted investigation report by ID."""
        record = (
            self.db.query(InvestigationRecord)
            .filter(InvestigationRecord.investigation_id == investigation_id)
            .first()
        )
        if not record:
            return None
        data = json.loads(record.report_json)
        data.pop("_request_context", None)
        return InvestigationReport(**data)

    def list_investigations(self, limit: int = 50) -> list[InvestigationReport]:
        """List recent investigations ordered from newest to oldest."""
        records = (
            self.db.query(InvestigationRecord)
            .order_by(InvestigationRecord.id.desc())
            .limit(limit)
            .all()
        )
        reports: list[InvestigationReport] = []
        for rec in records:
            try:
                data = json.loads(rec.report_json)
                data.pop("_request_context", None)
                reports.append(InvestigationReport(**data))
            except Exception:
                continue
        return reports

    def approve_and_apply_fix(
        self,
        investigation_id: str,
        approval: ApproveFixRequest,
    ) -> InvestigationReport:
        """Approve a remediation plan item, apply changes if permitted, and verify."""
        record = (
            self.db.query(InvestigationRecord)
            .filter(InvestigationRecord.investigation_id == investigation_id)
            .first()
        )
        if not record:
            raise KeyError(f"Investigation '{investigation_id}' not found.")

        raw_data = json.loads(record.report_json)
        req_ctx = raw_data.pop("_request_context", {}) or {}
        report = InvestigationReport(**raw_data)

        reconstructed_req = InvestigationRequest(
            title=report.title,
            prompt=report.prompt,
            url=report.target_url,
            method=report.http_method,
            headers=report.http_exchange.request_headers if report.http_exchange else {},
            query_params=report.http_exchange.query_params if report.http_exchange else {},
            repository_path=req_ctx.get("repository_path"),
            execute_live_request=False,
        )

        updated_report = self.orchestrator.approve_and_verify_fix(
            report=report,
            request=reconstructed_req,
            approval=approval,
        )
        self._save_report(updated_report, reconstructed_req)
        return updated_report

    def get_dashboard_overview(self) -> DashboardOverviewStats:
        """Compute live dashboard overview metrics from persisted database records."""
        reports = self.list_investigations(limit=100)
        total = len(reports)
        successful = sum(1 for r in reports if r.status in ("completed", "resolved"))
        open_issues = sum(
            len(r.findings) for r in reports if r.status != "resolved"
        )
        resolved_issues = sum(
            len(r.findings) for r in reports if r.status == "resolved"
        )

        category_dist: dict[str, int] = {
            "connectivity": 0,
            "authentication": 0,
            "request": 0,
            "schema": 0,
            "response": 0,
            "integration": 0,
        }
        severity_dist: dict[str, int] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "informational": 0,
        }
        recent_activity: list[InvestigationStepRecord] = []

        for r in reports:
            for f in r.findings:
                category_dist[f.category] = category_dist.get(f.category, 0) + 1
                severity_dist[f.severity] = severity_dist.get(f.severity, 0) + 1
            for step in reversed(r.timeline):
                if len(recent_activity) < 12:
                    recent_activity.append(step)

        return DashboardOverviewStats(
            total_investigations=total,
            successful_diagnoses=successful,
            open_issues=open_issues,
            resolved_issues=resolved_issues,
            category_distribution=category_dist,
            severity_distribution=severity_dist,
            recent_investigations=reports[:10],
            recent_activity=recent_activity,
        )

    def ensure_initial_diagnostic_baselines(self) -> None:
        """Run real deterministic investigations on startup if database is empty."""
        count = self.db.query(InvestigationRecord).count()
        if count > 0:
            return

        import base64

        expired_header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
        expired_payload = (
            base64.urlsafe_b64encode(
                json.dumps({"sub": "usr_91", "exp": int(time.time()) - 7200, "scope": "read:orders"}).encode()
            )
            .decode()
            .rstrip("=")
        )
        expired_jwt = f"{expired_header}.{expired_payload}.sig_sample"

        sample_openapi = {
            "openapi": "3.0.3",
            "info": {"title": "Orders Core API", "version": "1.0.0"},
            "servers": [{"url": "https://api.orders.example.com/v1"}],
            "paths": {
                "/orders": {
                    "post": {
                        "summary": "Create customer order",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["customer_id", "amount", "currency"],
                                        "properties": {
                                            "customer_id": {"type": "string"},
                                            "amount": {"type": "number"},
                                            "currency": {"type": "string", "enum": ["USD", "EUR", "GBP"]},
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {"201": {"description": "Created"}},
                    }
                }
            },
        }

        baseline_requests = [
            InvestigationRequest(
                title="POST /v1/orders — Expired JWT & Missing Required Schema Property",
                prompt="Why is my POST /v1/orders call failing authentication and schema validation?",
                url="https://api.orders.example.com/v1/orders",
                method="POST",
                headers={
                    "Authorization": f"Bearer {expired_jwt}",
                    "Content-Type": "application/json",
                },
                request_payload={"customer_id": "cust_402", "amount": "invalid_number_string"},
                simulated_response_status=401,
                simulated_response_headers={
                    "Content-Type": "application/json",
                    "WWW-Authenticate": 'Bearer error="invalid_token", error_description="The access token expired"',
                },
                simulated_response_body={"error": "invalid_token", "error_description": "Token expired"},
                openapi_spec=sample_openapi,
                required_scopes=["read:orders", "write:orders"],
                execute_live_request=False,
            ),
            InvestigationRequest(
                title="GET /v1/users/{id} — Unexpanded Path Parameter & Rate Limit 429",
                prompt="Diagnose rate limiting and path template failure on user profile fetch",
                url="https://api.orders.example.com/v1/users/{id}",
                method="GET",
                headers={"Accept": "application/json"},
                query_params={"filter": "undefined"},
                simulated_response_status=429,
                simulated_response_headers={
                    "Content-Type": "application/json",
                    "Retry-After": "30",
                    "X-RateLimit-Remaining": "0",
                },
                simulated_response_body={"message": "Too Many Requests - rate limit exceeded"},
                execute_live_request=False,
            ),
            InvestigationRequest(
                title="GET /v2/catalog — Unexpected HTML SSO Redirect & CORS Wildcard Conflict",
                prompt="Why is my frontend receiving an HTML page and CORS error instead of catalog JSON?",
                url="https://api.orders.example.com/v2/catalog",
                method="GET",
                headers={"Accept": "application/json", "Origin": "https://app.orders.example.com"},
                simulated_response_status=200,
                simulated_response_headers={
                    "Content-Type": "text/html; charset=utf-8",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Credentials": "true",
                },
                simulated_response_body="<!DOCTYPE html><html><body>Login Required</body></html>",
                expected_base_url="https://api.orders.example.com/v1",
                execute_live_request=False,
            ),
        ]

        for req in baseline_requests:
            self.create_and_run_investigation(req)
