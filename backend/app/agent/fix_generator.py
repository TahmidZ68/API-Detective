"""Agent Step 5 & Step 6: Safe fix generator, unified diff builder, thread-safe patch applier, and bounded rollback manager."""

from __future__ import annotations

import difflib
import re
import threading
from collections import OrderedDict
from pathlib import Path

from backend.app.core.exceptions import (
    ForbiddenRepairError,
    RepairApprovalRequiredError,
    RepositoryAccessError,
)
from backend.app.schemas.diagnostics import (
    DiagnosticFinding,
    InvestigationRequest,
    RemediationPlanItem,
    RepositoryAnalysisResult,
    RootCauseHypothesis,
)

FORBIDDEN_PATCH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"^\+.*\bverify\s*=\s*False\b", re.MULTILINE),
        "Disabling SSL/TLS certificate verification (verify=False) is strictly forbidden.",
    ),
    (
        re.compile(r"^\+.*\brejectUnauthorized\s*:\s*false\b", re.MULTILINE),
        "Disabling TLS verification (rejectUnauthorized: false) is strictly forbidden.",
    ),
    (
        re.compile(r"^\+.*\bNODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0", re.MULTILINE),
        "Disabling Node.js TLS verification is strictly forbidden.",
    ),
    (
        re.compile(
            r"^\+.*\b(?:sk-live-|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
            re.MULTILINE,
        ),
        "Introducing hardcoded production secrets or private keys in a patch is strictly forbidden.",
    ),
]

MAX_BACKUP_ENTRIES = 128
_BACKUP_LOCK = threading.RLock()
_FILE_LOCKS: dict[str, threading.RLock] = {}
# Bounded OrderedDict keyed by (investigation_scope, fix_id, resolved_file_path)
_FILE_BACKUP_REGISTRY: OrderedDict[tuple[str, str, str], str] = OrderedDict()


def _get_file_lock(resolved_path: str) -> threading.RLock:
    """Return a per-file re-entrant lock to serialize concurrent repairs on the same target file."""
    with _BACKUP_LOCK:
        lock = _FILE_LOCKS.get(resolved_path)
        if lock is None:
            lock = threading.RLock()
            _FILE_LOCKS[resolved_path] = lock
        return lock


def _store_backup(scope_id: str, fix_id: str, resolved_path: str, content: str) -> None:
    """Store a pre-modification file backup in the bounded LRU registry."""
    key = (scope_id, fix_id, resolved_path)
    with _BACKUP_LOCK:
        if key in _FILE_BACKUP_REGISTRY:
            _FILE_BACKUP_REGISTRY.move_to_end(key)
        _FILE_BACKUP_REGISTRY[key] = content
        while len(_FILE_BACKUP_REGISTRY) > MAX_BACKUP_ENTRIES:
            _FILE_BACKUP_REGISTRY.popitem(last=False)


def _pop_backup(scope_id: str, fix_id: str, resolved_path: str) -> str | None:
    """Retrieve and remove a file backup from the registry (falling back to global scope if needed)."""
    with _BACKUP_LOCK:
        primary_key = (scope_id, fix_id, resolved_path)
        if primary_key in _FILE_BACKUP_REGISTRY:
            return _FILE_BACKUP_REGISTRY.pop(primary_key)
        fallback_key = ("global", fix_id, resolved_path)
        if fallback_key in _FILE_BACKUP_REGISTRY:
            return _FILE_BACKUP_REGISTRY.pop(fallback_key)
        # Search any matching (fix_id, resolved_path) if investigation_id was not passed
        for k in list(_FILE_BACKUP_REGISTRY.keys()):
            if k[1] == fix_id and k[2] == resolved_path:
                return _FILE_BACKUP_REGISTRY.pop(k)
        return None


def cleanup_fix_backups(
    *,
    investigation_id: str | None = None,
    fix_id: str | None = None,
) -> int:
    """Explicitly purge stored file backups for a completed investigation or specific fix_id.

    Returns the number of backup entries removed.
    """
    removed = 0
    with _BACKUP_LOCK:
        keys_to_remove = [
            k
            for k in _FILE_BACKUP_REGISTRY
            if (investigation_id is None or k[0] == investigation_id)
            and (fix_id is None or k[1] == fix_id)
        ]
        for k in keys_to_remove:
            _FILE_BACKUP_REGISTRY.pop(k, None)
            removed += 1
    return removed


def get_backup_registry_size() -> int:
    """Return the current number of entries in the bounded backup registry."""
    with _BACKUP_LOCK:
        return len(_FILE_BACKUP_REGISTRY)


def validate_patch_safety(unified_diff: str) -> None:
    """Ensure a proposed patch never disables SSL, removes auth, or hardcodes secrets."""
    for pattern, reason in FORBIDDEN_PATCH_PATTERNS:
        if pattern.search(unified_diff):
            raise ForbiddenRepairError(reason)


def _compute_modified_source(original_text: str, finding_id: str, finding_title: str) -> str:
    """Compute a safe, minimal deterministic source modification preserving unrelated user code."""
    modified = original_text
    if "verify=False" in modified and (finding_id == "INT-007" or "tls" in finding_title.lower()):
        modified = modified.replace("verify=False", "verify=True")
    elif "rejectUnauthorized: false" in modified:
        modified = modified.replace("rejectUnauthorized: false", "rejectUnauthorized: true")
    elif "Bearer Bearer " in modified and (
        finding_id == "AUTH-004" or "bearer" in finding_title.lower()
    ):
        modified = modified.replace("Bearer Bearer ", "Bearer ")
    elif (
        finding_id == "INT-007"
        and "timeout" in finding_title.lower()
        and "timeout=" not in modified
    ):
        modified = re.sub(
            r"(requests\.(?:get|post|put|delete|patch)\([^)\n]+)\)",
            r"\1, timeout=10)",
            modified,
            count=1,
        )
    return modified


def _generate_repo_patch(
    repo_root: Path,
    rel_file: str,
    finding: DiagnosticFinding,
) -> str | None:
    """Generate a reviewable unified diff for deterministic repository fixes when applicable."""
    candidate = repo_root / rel_file
    if candidate.is_symlink():
        return None
    target = candidate.resolve()
    if not target.exists() or not target.is_file() or repo_root not in target.parents:
        return None
    try:
        original_text = target.read_text(encoding="utf-8")
    except Exception:
        return None

    modified_text = _compute_modified_source(original_text, finding.diagnostic_id, finding.title)
    if modified_text == original_text:
        return None

    diff_lines = list(
        difflib.unified_diff(
            original_text.splitlines(keepends=True),
            modified_text.splitlines(keepends=True),
            fromfile=f"a/{rel_file}",
            tofile=f"b/{rel_file}",
        )
    )
    if not diff_lines:
        return None
    diff_str = "".join(diff_lines)
    validate_patch_safety(diff_str)
    return diff_str


def _generate_request_config_diff(
    request: InvestigationRequest,
    finding: DiagnosticFinding,
) -> str:
    """Generate an illustrative configuration diff showing the exact request repair."""
    before_lines = [
        f"method: {request.method.upper()}",
        f"url: {request.url or '<MISSING_URL>'}",
    ]
    for k, v in (request.headers or {}).items():
        before_lines.append(f"header[{k}]: {v if 'auth' not in k.lower() else 'Bearer <TOKEN>'}")

    after_lines = list(before_lines)
    if finding.diagnostic_id == "AUTH-001":
        after_lines.append("header[Authorization]: Bearer <YOUR_VALID_ACCESS_TOKEN>")
    elif finding.diagnostic_id in ("AUTH-002", "AUTH-003"):
        after_lines = [
            line
            if not line.lower().startswith("header[authorization]")
            else "header[Authorization]: Bearer <REFRESHED_VALID_ACCESS_TOKEN>"
            for line in after_lines
        ]
    elif finding.diagnostic_id == "AUTH-004":
        after_lines = [
            line
            if not line.lower().startswith("header[authorization]")
            else "header[Authorization]: Bearer <SINGLE_SCHEME_ACCESS_TOKEN>"
            for line in after_lines
        ]
    elif finding.diagnostic_id in ("REQ-002", "REQ-003"):
        if not any(line.lower().startswith("header[content-type]") for line in after_lines):
            after_lines.append("header[Content-Type]: application/json")
        else:
            after_lines = [
                "header[Content-Type]: application/json"
                if line.lower().startswith("header[content-type]")
                else line
                for line in after_lines
            ]
    elif finding.diagnostic_id == "INT-004":
        for ev in finding.evidence:
            if "Closest documented path(s):" in ev:
                suggested = ev.split("Closest documented path(s):")[1].strip().split(",")[0].strip()
                if request.url:
                    from urllib.parse import urlparse, urlunparse

                    p = urlparse(request.url)
                    fixed_url = urlunparse(
                        (p.scheme, p.netloc, suggested, p.params, p.query, p.fragment)
                    )
                    after_lines[1] = f"url: {fixed_url}"
    else:
        after_lines.append(f"# Recommended fix: {finding.recommendation}")

    diff = difflib.unified_diff(
        [line + "\n" for line in before_lines],
        [line + "\n" for line in after_lines],
        fromfile="a/request_config.yaml",
        tofile="b/request_config.yaml",
    )
    return "".join(diff)


def generate_remediation_plan(
    *,
    request: InvestigationRequest,
    findings: list[DiagnosticFinding],
    root_causes: list[RootCauseHypothesis],
    repository_analysis: RepositoryAnalysisResult | None = None,
) -> list[RemediationPlanItem]:
    """Step 5: Build structured remediation plan items (Levels 1 & 2) from ranked root causes."""
    plan_items: list[RemediationPlanItem] = []
    finding_by_id = {f.diagnostic_id: f for f in findings}
    repo_root = (
        Path(repository_analysis.repository_path).resolve() if repository_analysis else None
    )

    for idx, rc in enumerate(root_causes, start=1):
        primary_id = rc.related_diagnostic_ids[0] if rc.related_diagnostic_ids else ""
        finding = next(
            (f for f in findings if f.diagnostic_id == primary_id and f.title == rc.title),
            finding_by_id.get(primary_id) or (findings[0] if findings else None),
        )
        if finding is None:
            continue

        affected_files: list[str] = []
        if "file_path" in finding.metadata:
            affected_files.append(str(finding.metadata["file_path"]))
        elif repository_analysis:
            for rf in repository_analysis.findings:
                if rf.file_path not in affected_files:
                    if (
                        finding.category == "authentication" and rf.pattern_type == "auth_config"
                    ) or (
                        finding.category == "integration"
                        and rf.pattern_type
                        in ("endpoint", "config_mismatch", "request_construction")
                    ):
                        affected_files.append(rf.file_path)

        unified_diff: str | None = None
        repair_level = 1
        if repo_root and affected_files:
            for af in affected_files:
                unified_diff = _generate_repo_patch(repo_root, af, finding)
                if unified_diff:
                    repair_level = 2
                    break

        if unified_diff is None:
            unified_diff = _generate_request_config_diff(request, finding)
            repair_level = 2 if unified_diff else 1

        risk_level = (
            "medium" if finding.category in ("authentication", "connectivity") else "low"
        )

        plan_items.append(
            RemediationPlanItem(
                fix_id=f"FIX-{idx:03d}",
                problem=rc.title,
                evidence=rc.supporting_evidence,
                root_cause=rc.explanation,
                recommended_solution=finding.recommendation,
                affected_files=affected_files,
                risk_level=risk_level,  # type: ignore[arg-type]
                repair_level=repair_level,
                unified_diff=unified_diff,
                requires_approval=True,
                approved=False,
                applied=False,
                verification_procedure=(
                    f"Re-run API Detective diagnostics ({finding.diagnostic_id}) and verify the endpoint returns an expected 2xx response with 0 high/critical findings."
                ),
            )
        )

    return plan_items


def apply_approved_fix(
    *,
    fix_item: RemediationPlanItem,
    approved: bool,
    repository_path: str | Path | None = None,
    investigation_id: str | None = None,
) -> RemediationPlanItem:
    """Step 6 (Level 3): Apply a repair patch with per-file locking, scoped backup, and transactional rollback."""
    if not approved:
        raise RepairApprovalRequiredError(
            f"Fix '{fix_item.fix_id}' cannot be applied without explicit developer approval."
        )

    if fix_item.unified_diff:
        validate_patch_safety(fix_item.unified_diff)

    fix_item.approved = True
    scope_id = investigation_id or "global"

    if repository_path and fix_item.affected_files and fix_item.unified_diff:
        root = Path(repository_path).resolve()
        # Resolve and validate all target paths upfront, sorting deterministically to prevent AB-BA lock deadlocks
        validated_targets: list[Path] = []
        for rel_file in fix_item.affected_files:
            candidate = root / rel_file
            if candidate.is_symlink():
                raise RepositoryAccessError(
                    f"Refusing to modify symlinked file '{rel_file}'."
                )
            target = candidate.resolve()
            if root not in target.parents or not target.exists() or not target.is_file():
                raise RepositoryAccessError(
                    f"Target file '{rel_file}' is outside the authorized repository root."
                )
            if target not in validated_targets:
                validated_targets.append(target)
        validated_targets.sort(key=lambda p: str(p))

        from contextlib import ExitStack

        modified_targets: list[tuple[Path, str]] = []
        with ExitStack() as lock_stack:
            for target in validated_targets:
                lock_stack.enter_context(_get_file_lock(str(target)))
            try:
                for target in validated_targets:
                    original_content = target.read_text(encoding="utf-8")
                    _store_backup(scope_id, fix_item.fix_id, str(target), original_content)
                    modified_targets.append((target, original_content))

                    updated = original_content
                    if "+    " in fix_item.unified_diff or "verify=True" in fix_item.unified_diff:
                        if "verify=False" in updated:
                            updated = updated.replace("verify=False", "verify=True")
                    if "rejectUnauthorized: true" in fix_item.unified_diff:
                        updated = updated.replace(
                            "rejectUnauthorized: false", "rejectUnauthorized: true"
                        )
                    if "Bearer " in fix_item.unified_diff and "Bearer Bearer " in updated:
                        updated = updated.replace("Bearer Bearer ", "Bearer ")
                    if "timeout=10" in fix_item.unified_diff and "timeout=" not in updated:
                        updated = re.sub(
                            r"(requests\.(?:get|post|put|delete|patch)\([^)\n]+)\)",
                            r"\1, timeout=10)",
                            updated,
                            count=1,
                        )
                    if updated != original_content:
                        target.write_text(updated, encoding="utf-8")
            except Exception:
                for target_path, orig_text in modified_targets:
                    target_path.write_text(orig_text, encoding="utf-8")
                    _pop_backup(scope_id, fix_item.fix_id, str(target_path))
                raise

    fix_item.applied = True
    fix_item.repair_level = 3
    return fix_item


def rollback_approved_fix(
    *,
    fix_item: RemediationPlanItem,
    repository_path: str | Path,
    investigation_id: str | None = None,
    cleanup_backup: bool = True,
) -> bool:
    """Restore backed-up file contents for a previously applied fix and clean up the backup entry."""
    root = Path(repository_path).resolve()
    scope_id = investigation_id or "global"
    restored_any = False

    for rel_file in fix_item.affected_files:
        target = (root / rel_file).resolve()
        if not target.exists() or root not in target.parents:
            continue
        file_lock = _get_file_lock(str(target))
        with file_lock:
            if cleanup_backup:
                backup = _pop_backup(scope_id, fix_item.fix_id, str(target))
            else:
                with _BACKUP_LOCK:
                    backup = _FILE_BACKUP_REGISTRY.get(
                        (scope_id, fix_item.fix_id, str(target))
                    ) or _FILE_BACKUP_REGISTRY.get(("global", fix_item.fix_id, str(target)))
            if backup is not None:
                target.write_text(backup, encoding="utf-8")
                restored_any = True

    if restored_any:
        fix_item.applied = False
        fix_item.repair_level = 2
    return restored_any
