"""Export investigation reports to JSON, Markdown, and standalone HTML formats."""

from __future__ import annotations

import html
import json

from backend.app.schemas.diagnostics import InvestigationReport


def export_report_json(report: InvestigationReport) -> str:
    """Serialize an InvestigationReport to formatted JSON."""
    return json.dumps(report.model_dump(), indent=2)


def export_report_markdown(report: InvestigationReport) -> str:
    """Format an InvestigationReport as a comprehensive Markdown document."""
    lines: list[str] = [
        f"# API Detective Diagnostic Report — `{report.investigation_id}`",
        "",
        f"- **Title:** {report.title}",
        f"- **Status:** `{report.status.upper()}`",
        f"- **Target URL:** `{report.target_url or 'N/A'}`",
        f"- **HTTP Method:** `{report.http_method}`",
        f"- **Created At:** `{report.created_at}`",
        f"- **Completed At:** `{report.completed_at or 'N/A'}`",
        "",
        "## Executive Summary",
        "",
        report.summary or "No summary available.",
        "",
        "## Agent Execution Timeline",
        "",
        "| Step | Phase | Tool | Summary | Duration (ms) |",
        "|------|-------|------|---------|---------------|",
    ]
    for step in report.timeline:
        lines.append(
            f"| {step.step_number} | `{step.phase}` | `{step.tool_name or '-'}` | {step.summary} | {step.duration_ms:.2f} |"
        )

    lines.extend(["", "## Root-Cause Hypotheses", ""])
    if not report.root_causes:
        lines.append("_No root-cause hypotheses identified._")
    else:
        for rc in report.root_causes:
            lines.extend(
                [
                    f"### #{rc.rank}: {rc.title} (`{int(rc.confidence * 100)}%` confidence — `{rc.status}`)",
                    f"- **Category:** `{rc.category}`",
                    f"- **Related Diagnostics:** `{', '.join(rc.related_diagnostic_ids)}`",
                    f"- **Explanation:** {rc.explanation}",
                    "- **Supporting Evidence:**",
                    *[f"  - {ev}" for ev in rc.supporting_evidence],
                    "",
                ]
            )

    lines.extend(["## Deterministic Findings", ""])
    if not report.findings:
        lines.append("_No diagnostic issues detected._")
    else:
        for f in report.findings:
            lines.extend(
                [
                    f"### `[{f.diagnostic_id}]` {f.title} (`{f.severity.upper()}` / `{f.status}`)",
                    f"- **Category:** `{f.category}` | **Confidence:** `{int(f.confidence * 100)}%`",
                    f"- **Description:** {f.description}",
                    f"- **Recommendation:** {f.recommendation}",
                    "- **Evidence:**",
                    *[f"  - `{ev}`" for ev in f.evidence],
                    "",
                ]
            )

    lines.extend(["## Remediation Plan", ""])
    if not report.remediation_plan:
        lines.append("_No remediation required._")
    else:
        for fix in report.remediation_plan:
            lines.extend(
                [
                    f"### `{fix.fix_id}` — {fix.problem}",
                    f"- **Risk Level:** `{fix.risk_level}` | **Repair Level:** `Level {fix.repair_level}` | **Applied:** `{fix.applied}`",
                    f"- **Root Cause:** {fix.root_cause}",
                    f"- **Recommended Solution:** {fix.recommended_solution}",
                    f"- **Verification Procedure:** {fix.verification_procedure}",
                ]
            )
            if fix.unified_diff:
                lines.extend(["", "```diff", fix.unified_diff.rstrip(), "```", ""])

    if report.verification:
        v = report.verification
        lines.extend(
            [
                "## Verification Results",
                "",
                f"- **Fix Worked:** `{v.fix_worked}`",
                f"- **Summary:** {v.summary}",
                "- **Passed Checks:**",
                *[f"  - {c}" for c in v.passed_checks],
            ]
        )
        if v.remaining_problems:
            lines.extend(["- **Remaining Problems:**", *[f"  - {p}" for p in v.remaining_problems]])

    return "\n".join(lines) + "\n"


def export_report_html(report: InvestigationReport) -> str:
    """Render an InvestigationReport as a standalone, dark-mode HTML diagnostic report."""
    esc = html.escape
    findings_rows = "".join(
        f"""
        <div class="card">
          <div class="badge-row">
            <span class="mono">{esc(f.diagnostic_id)}</span>
            <span class="sev sev-{esc(f.severity)}">{esc(f.severity.upper())}</span>
            <span class="status">{esc(f.status)} ({int(f.confidence * 100)}%)</span>
          </div>
          <h3>{esc(f.title)}</h3>
          <p>{esc(f.description)}</p>
          <p class="rec"><strong>Recommendation:</strong> {esc(f.recommendation)}</p>
          <ul>{"".join(f"<li><code>{esc(ev)}</code></li>" for ev in f.evidence)}</ul>
        </div>
        """
        for f in report.findings
    ) or "<p>No deterministic issues detected.</p>"

    fixes_rows = "".join(
        f"""
        <div class="card">
          <h3>{esc(fix.fix_id)} — {esc(fix.problem)}</h3>
          <p><strong>Solution:</strong> {esc(fix.recommended_solution)}</p>
          <p><strong>Risk:</strong> {esc(fix.risk_level.upper())} | <strong>Repair Level:</strong> {fix.repair_level}</p>
          {f'<pre><code>{esc(fix.unified_diff)}</code></pre>' if fix.unified_diff else ''}
        </div>
        """
        for fix in report.remediation_plan
    ) or "<p>No remediation items required.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>API Detective Report — {esc(report.investigation_id)}</title>
  <style>
    body {{ background: #0b0f19; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 32px; line-height: 1.5; }}
    .container {{ max-width: 980px; margin: 0 auto; }}
    h1, h2, h3 {{ color: #f8fafc; }}
    .meta {{ background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 24px; }}
    .card {{ background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
    .badge-row {{ display: flex; gap: 10px; align-items: center; margin-bottom: 8px; font-size: 12px; }}
    .mono, code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    .sev {{ padding: 2px 8px; border-radius: 4px; font-weight: 600; }}
    .sev-critical {{ background: #7f1d1d; color: #fecaca; }}
    .sev-high {{ background: #7c2d12; color: #fed7aa; }}
    .sev-medium {{ background: #713f12; color: #fef08a; }}
    .sev-low, .sev-informational {{ background: #1e3a8a; color: #bfdbfe; }}
    pre {{ background: #030712; padding: 12px; border-radius: 6px; overflow-x: auto; border: 1px solid #1e293b; }}
    .rec {{ color: #93c5fd; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>API Detective Diagnostic Report</h1>
    <div class="meta">
      <p><strong>ID:</strong> <span class="mono">{esc(report.investigation_id)}</span> | <strong>Status:</strong> {esc(report.status.upper())}</p>
      <p><strong>Target:</strong> <span class="mono">{esc(report.http_method)} {esc(report.target_url or 'N/A')}</span></p>
      <p><strong>Summary:</strong> {esc(report.summary)}</p>
    </div>
    <h2>Diagnostic Findings ({len(report.findings)})</h2>
    {findings_rows}
    <h2>Remediation Plan ({len(report.remediation_plan)})</h2>
    {fixes_rows}
  </div>
</body>
</html>"""
