"""Agent Step 4: Evidence-based root-cause ranking engine."""

from __future__ import annotations

from backend.app.schemas.diagnostics import (
    DiagnosticFinding,
    RepositoryAnalysisResult,
    RootCauseHypothesis,
)

SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 0.15,
    "high": 0.10,
    "medium": 0.05,
    "low": 0.02,
    "informational": 0.0,
}


def rank_root_causes(
    findings: list[DiagnosticFinding],
    repository_analysis: RepositoryAnalysisResult | None = None,
) -> list[RootCauseHypothesis]:
    """Combine deterministic findings and repository evidence into ranked root-cause hypotheses."""
    if not findings:
        return []

    # Group related findings so primary root causes aren't fragmented
    # E.g. AUTH-003 (Expired JWT) + AUTH-008 (401 Unauthorized) -> Expired JWT is the primary cause of the 401
    has_specific_auth = any(
        f.diagnostic_id in ("AUTH-001", "AUTH-002", "AUTH-003", "AUTH-004", "AUTH-005", "AUTH-006", "AUTH-007")
        for f in findings
    )
    has_specific_req_or_schema = any(
        f.category in ("request", "schema") and f.diagnostic_id != "RES-001" for f in findings
    )

    scored_items: list[tuple[float, DiagnosticFinding, list[str], list[str]]] = []

    for f in findings:
        # Suppress generic symptom findings (like AUTH-008 401 or RES-001 400/422) when a specific root cause exists
        if f.diagnostic_id == "AUTH-008" and has_specific_auth:
            continue
        if f.diagnostic_id == "RES-001" and "400" in f.title and has_specific_req_or_schema:
            continue
        if f.diagnostic_id == "RES-001" and "422" in f.title and has_specific_req_or_schema:
            continue

        evidence = list(f.evidence)
        related_ids = [f.diagnostic_id]

        # Attach symptom evidence if relevant
        if f.category == "authentication":
            for sym in findings:
                if sym.diagnostic_id == "AUTH-008" and sym.diagnostic_id not in related_ids:
                    related_ids.append(sym.diagnostic_id)
                    evidence.extend(sym.evidence[:1])
        elif f.category in ("request", "schema"):
            for sym in findings:
                if sym.diagnostic_id == "RES-001" and sym.diagnostic_id not in related_ids:
                    related_ids.append(sym.diagnostic_id)
                    evidence.extend(sym.evidence[:1])

        # Correlate with repository locations if available
        if repository_analysis and repository_analysis.findings:
            for rf in repository_analysis.findings:
                if (
                    f.category == "authentication" and rf.pattern_type in ("auth_config", "env_reference")
                ) or (
                    f.category == "integration" and rf.pattern_type in ("endpoint", "config_mismatch")
                ):
                    loc_ev = f"Repository source location: {rf.file_path}:{rf.line_number} ({rf.note})"
                    if loc_ev not in evidence:
                        evidence.append(loc_ev)
                    break

        score = f.confidence + SEVERITY_WEIGHT.get(f.severity, 0.0)
        scored_items.append((score, f, evidence, related_ids))

    # If all findings were filtered as symptoms, keep original findings
    if not scored_items:
        for f in findings:
            score = f.confidence + SEVERITY_WEIGHT.get(f.severity, 0.0)
            scored_items.append((score, f, list(f.evidence), [f.diagnostic_id]))

    scored_items.sort(key=lambda item: item[0], reverse=True)

    hypotheses: list[RootCauseHypothesis] = []
    for rank_idx, (_, finding, evidence, related_ids) in enumerate(scored_items, start=1):
        hypotheses.append(
            RootCauseHypothesis(
                hypothesis_id=f"RC-{rank_idx:03d}",
                rank=rank_idx,
                title=finding.title,
                category=finding.category,
                confidence=round(min(1.0, finding.confidence), 2),
                status=finding.status,
                explanation=finding.description,
                supporting_evidence=evidence,
                related_diagnostic_ids=related_ids,
            )
        )

    return hypotheses
