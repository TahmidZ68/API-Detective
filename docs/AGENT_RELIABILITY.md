# API Detective — Agent Reliability Audit (`v0.1.0-alpha.2`)

This document audits the 13 reliability requirements of the **API Detective** agent orchestration engine (`backend/app/agent/`).

---

## 1. End-to-End Lifecycle Verification Matrix

| Step | Capability | Implementation Module | Verification Behavior |
|------|------------|-----------------------|-----------------------|
| 1 | Receive an actual debugging task | `planner.py:extract_task_context` | Parses natural-language prompt, URL, method, headers, payload, spec, error log, and repository path. |
| 2 | Understand available evidence | `planner.py:extract_task_context` | Flags available evidence domains (`has_url`, `has_openapi_spec`, `has_schemas`, `has_repository`, `has_error_log`). |
| 3 | Construct an investigation plan | `planner.py:build_investigation_plan` | Dynamically orders `InvestigationPlanStep` items with explicit rationale for each selected tool. |
| 4 | Select appropriate diagnostic tools | `planner.py:build_investigation_plan` | Only schedules `openapi_parser` when a spec is provided, `repository_inspector` when a repo is provided, and `http_client` when live execution is enabled. |
| 5 | Execute the tools | `investigator.py:ToolExecutor` | Invokes real deterministic functions, captures wall-clock `duration_ms`, and enforces per-tool timeouts (`ToolExecutionTimeoutError`). |
| 6 | Interpret actual results | `investigator.py:ToolExecutor` | Deduplicates findings by `(diagnostic_id, title)` and records exact finding codes in the audit timeline. |
| 7 | Develop competing root-cause hypotheses | `root_cause.py:rank_root_causes` | Correlates HTTP, schema, and repository evidence into multiple ranked `RootCauseHypothesis` entries. |
| 8 | Rank hypotheses based on evidence | `root_cause.py:rank_root_causes` | Ranks primary causes (e.g., `AUTH-003` Expired JWT or `SCH-001` Missing Property) above downstream symptoms (`AUTH-008` 401 or `RES-001` 422). |
| 9 | Generate actionable fixes | `fix_generator.py:generate_remediation_plan` | Produces Level 1 explanations and Level 2 unified diffs (`difflib.unified_diff`) validated by `validate_patch_safety()`. |
| 10 | Request authorization for code edits | `fix_generator.py:apply_approved_fix` | Sets `requires_approval=True`; raises `RepairApprovalRequiredError` if called with `approved=False`. |
| 11 | Apply an approved patch | `fix_generator.py:apply_approved_fix` | Snapshots original files in `_FILE_BACKUP_REGISTRY`, applies minimal targeted changes, and rolls back automatically on failure. |
| 12 | Run verification | `verifier.py:verify_remediation` | Re-scans the repository (`inspect_repository`) and re-runs deterministic diagnostics (`run_diagnostic_verification`) against post-fix state. |
| 13 | Report the actual outcome | `test_runner.py:run_diagnostic_verification` | Reports `fix_worked=False` whenever critical/high findings remain unresolved; lists `passed_checks`, `failed_checks`, `remaining_problems`, and `unverified_assumptions`. |

---

## 2. Specific Reliability Safeguards Audited

1. **No Fabricated Tool Execution**: Every `InvestigationStepRecord` in `report.timeline` is generated directly from an executed Python function in `ToolExecutor.execute_plan`.
2. **No Unconditional Successful Verification**: In `v0.1.0-alpha.2`, `verify_remediation` re-runs `inspect_repository()` on disk and evaluates `run_all_diagnostics()`. If a repository defect was not resolved on disk, `fix_worked` evaluates to `False` and `failed_checks` lists the active high/critical findings.
3. **Bounded Loops & Duplicate Call Prevention**: `ToolExecutor` strictly enforces `max_tool_steps = max(1, self.max_iterations * 2)` and tracks `executed_signatures` (`(tool_name, url, method)`) to prevent redundant identical tool invocations.
4. **Graceful LLM Provider Degradation**: When `LLM_PROVIDER=none` or an external LLM endpoint times out/errors, `LLMProviderAdapter.synthesize_summary` logs a warning and falls back to `_build_deterministic_summary(report)` without failing the investigation.
5. **Cancellation Support**: `AgentOrchestrator.cancel_investigation(id)` halts execution at phase boundaries and returns `status="cancelled"`.
