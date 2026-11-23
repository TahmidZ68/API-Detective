"""Multi-step Agent Orchestrator implementing the 7-stage API Detective lifecycle.

Lifecycle:
  Step 1: Understand the task
  Step 2: Build an investigation plan
  Step 3: Execute diagnostic tools
  Step 4: Analyze evidence & rank root causes
  Step 5: Generate a remediation plan
  Step 6: Apply approved changes (only with explicit permission)
  Step 7: Verify repairs
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx

from backend.app.agent.fix_generator import apply_approved_fix, generate_remediation_plan
from backend.app.agent.investigator import ToolExecutor
from backend.app.agent.planner import build_investigation_plan, extract_task_context
from backend.app.agent.root_cause import rank_root_causes
from backend.app.agent.verifier import verify_remediation
from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.core.security import redact_url
from backend.app.providers.llm import get_llm_provider
from backend.app.schemas.diagnostics import (
    ApproveFixRequest,
    InvestigationReport,
    InvestigationRequest,
    InvestigationStepRecord,
)

logger = get_logger("api_detective.agent")


class AgentOrchestrator:
    """Autonomous, bounded tool-using API investigation agent."""

    def __init__(
        self,
        *,
        max_iterations: int | None = None,
        tool_timeout_seconds: float | None = None,
        http_transport: httpx.BaseTransport | None = None,
    ):
        settings = get_settings()
        self.max_iterations = max_iterations or settings.agent_max_iterations
        self.tool_timeout_seconds = tool_timeout_seconds or settings.agent_tool_timeout_seconds
        self.http_transport = http_transport
        self._cancelled_ids: set[str] = set()

    def cancel_investigation(self, investigation_id: str) -> None:
        """Mark an active investigation ID for cancellation."""
        self._cancelled_ids.add(investigation_id)

    def run_investigation(
        self,
        request: InvestigationRequest,
        *,
        investigation_id: str | None = None,
    ) -> InvestigationReport:
        """Execute a complete multi-step investigation and return a structured report."""
        timeline: list[InvestigationStepRecord] = []

        # Step 1 — Understand the task
        t0 = time.perf_counter()
        context = extract_task_context(request)
        timeline.append(
            InvestigationStepRecord(
                step_number=1,
                phase="understand",
                summary=f"Extracted task context (focus: {', '.join(context['inferred_focus'])})",
                details=context,
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
        )

        report = InvestigationReport(
            title=context["title"],
            prompt=request.prompt,
            status="running",
            target_url=redact_url(request.url) if request.url else None,
            http_method=request.method.upper(),
        )
        if investigation_id:
            report.investigation_id = investigation_id

        if report.investigation_id in self._cancelled_ids:
            report.status = "cancelled"
            report.summary = "Investigation cancelled before planning."
            return report

        # Step 2 — Build an investigation plan
        t1 = time.perf_counter()
        plan = build_investigation_plan(request, context)
        report.plan = plan
        timeline.append(
            InvestigationStepRecord(
                step_number=2,
                phase="plan",
                summary=f"Constructed {len(plan)}-step tool execution plan",
                details={"planned_tools": [p.tool_name for p in plan]},
                duration_ms=round((time.perf_counter() - t1) * 1000, 2),
            )
        )

        # Step 3 — Execute diagnostic tools
        executor = ToolExecutor(
            max_iterations=self.max_iterations,
            tool_timeout_seconds=self.tool_timeout_seconds,
            http_transport=self.http_transport,
        )
        exec_result = executor.execute_plan(request, plan, start_step_number=3)
        findings = exec_result["findings"]
        timeline.extend(exec_result["timeline"])
        report.http_exchange = exec_result["exchange"]
        report.repository_analysis = exec_result["repository_analysis"]
        report.findings = findings

        next_step_num = len(timeline) + 1

        if report.investigation_id in self._cancelled_ids:
            report.status = "cancelled"
            report.timeline = timeline
            report.summary = "Investigation cancelled after tool execution."
            return report

        # Step 4 — Analyze evidence & rank root causes
        t2 = time.perf_counter()
        root_causes = rank_root_causes(findings, report.repository_analysis)
        report.root_causes = root_causes
        timeline.append(
            InvestigationStepRecord(
                step_number=next_step_num,
                phase="analyze",
                summary=(
                    f"Ranked {len(root_causes)} root-cause hypothesis/hypotheses "
                    f"(top: {root_causes[0].title} @ {int(root_causes[0].confidence * 100)}% confidence)"
                    if root_causes
                    else "Analyzed all tool outputs; no integration defects detected"
                ),
                details={
                    "root_causes_count": len(root_causes),
                    "top_hypothesis": root_causes[0].title if root_causes else None,
                },
                duration_ms=round((time.perf_counter() - t2) * 1000, 2),
            )
        )
        next_step_num += 1

        # Step 5 — Generate a remediation plan
        t3 = time.perf_counter()
        remediation_plan = generate_remediation_plan(
            request=request,
            findings=findings,
            root_causes=root_causes,
            repository_analysis=report.repository_analysis,
        )
        report.remediation_plan = remediation_plan
        timeline.append(
            InvestigationStepRecord(
                step_number=next_step_num,
                phase="remediate",
                summary=f"Generated {len(remediation_plan)} actionable remediation proposal(s) with reviewable diffs",
                details={"fix_ids": [item.fix_id for item in remediation_plan]},
                duration_ms=round((time.perf_counter() - t3) * 1000, 2),
            )
        )

        # Optional LLM synthesis (gracefully skipped when provider is 'none' or unavailable)
        llm_adapter = get_llm_provider()
        deterministic_summary = self._build_deterministic_summary(report)
        if llm_adapter.is_available and findings:
            llm_summary = llm_adapter.synthesize_summary(
                task_description=report.title,
                findings_summary=[
                    {
                        "id": f.diagnostic_id,
                        "title": f.title,
                        "severity": f.severity,
                        "confidence": f.confidence,
                        "recommendation": f.recommendation,
                    }
                    for f in findings[:6]
                ],
            )
            if llm_summary:
                report.llm_assisted = True
                report.llm_provider_used = llm_adapter.provider
                report.summary = llm_summary
            else:
                report.summary = deterministic_summary
        else:
            report.summary = deterministic_summary

        report.timeline = timeline
        report.status = "completed"
        report.completed_at = datetime.now(UTC).isoformat()
        logger.info(
            "investigation_completed",
            investigation_id=report.investigation_id,
            findings_count=len(findings),
            root_causes_count=len(root_causes),
        )
        return report

    def approve_and_verify_fix(
        self,
        *,
        report: InvestigationReport,
        request: InvestigationRequest,
        approval: ApproveFixRequest,
    ) -> InvestigationReport:
        """Steps 6 & 7: Apply an explicitly approved fix and run verification diagnostics."""
        target_fix = next(
            (item for item in report.remediation_plan if item.fix_id == approval.fix_id),
            None,
        )
        if target_fix is None:
            raise ValueError(f"Fix ID '{approval.fix_id}' not found in remediation plan.")

        next_step = len(report.timeline) + 1
        t0 = time.perf_counter()

        # Step 6 — Apply approved changes
        apply_approved_fix(
            fix_item=target_fix,
            approved=approval.approved,
            repository_path=request.repository_path if approval.apply_changes else None,
            investigation_id=report.investigation_id,
        )
        report.timeline.append(
            InvestigationStepRecord(
                step_number=next_step,
                phase="apply_fix",
                tool_name="fix_generator",
                summary=f"Developer approved and applied fix {target_fix.fix_id} ({target_fix.problem})",
                details={"fix_id": target_fix.fix_id, "affected_files": target_fix.affected_files},
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
        )
        next_step += 1

        # Step 7 — Verify
        if approval.run_verification:
            t1 = time.perf_counter()
            verification = verify_remediation(
                request=request,
                previous_findings=report.findings,
                remediation_plan=report.remediation_plan,
                updated_exchange=None,
            )
            report.verification = verification
            if verification.fix_worked:
                report.status = "resolved"
            report.timeline.append(
                InvestigationStepRecord(
                    step_number=next_step,
                    phase="verify",
                    tool_name="test_runner",
                    summary=verification.summary,
                    details={
                        "fix_worked": verification.fix_worked,
                        "passed_checks": verification.passed_checks,
                        "remaining_problems": verification.remaining_problems,
                    },
                    duration_ms=round((time.perf_counter() - t1) * 1000, 2),
                )
            )

        return report

    @staticmethod
    def _build_deterministic_summary(report: InvestigationReport) -> str:
        if not report.findings:
            return (
                f"Completed {len(report.plan)}-step investigation for '{report.title}'. "
                "No deterministic connectivity, authentication, request, schema, response, or integration issues were detected."
            )
        top_rc = report.root_causes[0] if report.root_causes else None
        if top_rc:
            return (
                f"Identified {len(report.findings)} finding(s) across {len(report.plan)} diagnostic steps. "
                f"Primary root cause ({int(top_rc.confidence * 100)}% confidence, {top_rc.status}): "
                f"{top_rc.title} — {top_rc.explanation}"
            )
        top_f = report.findings[0]
        return (
            f"Identified {len(report.findings)} diagnostic finding(s). "
            f"Highest severity issue ({top_f.diagnostic_id}): {top_f.title}."
        )
