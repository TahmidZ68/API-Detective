# API Detective Agent Workflow & Lifecycle

API Detective implements an autonomous, bounded, 7-step investigation workflow (`backend/app/agent/orchestrator.py`) that prioritizes deterministic evidence over speculative AI responses.

## The 7-Step Investigation Lifecycle

### Step 1 — Understand the Task (`planner.py:extract_task_context`)
Parses the user's natural-language symptom prompt, target endpoint URL, HTTP method, headers, payloads, schemas, error logs, and repository path to infer diagnostic focus domains (`connectivity`, `authentication`, `request`, `schema`, `response`, `integration`).

### Step 2 — Build an Investigation Plan (`planner.py:build_investigation_plan`)
Selects and orders the exact set of diagnostic tools required for the current evidence context (`log_analyzer`, `openapi_parser`, `http_client`, `connectivity_diagnostics`, `authentication_diagnostics`, `request_diagnostics`, `schema_diagnostics`, `response_diagnostics`, `repository_inspector`, `integration_diagnostics`).

### Step 3 — Execute Diagnostic Tools (`investigator.py:ToolExecutor`)
Executes each planned tool sequentially within configurable iteration (`AGENT_MAX_ITERATIONS`) and per-tool execution timeout (`AGENT_TOOL_TIMEOUT_SECONDS`) bounds. Records every tool invocation, duration, and finding code in the auditable `timeline`.

### Step 4 — Analyze Evidence & Rank Root Causes (`root_cause.py:rank_root_causes`)
Combines deterministic findings with OpenAPI contract and repository file/line evidence. Suppresses generic downstream symptoms (such as `AUTH-008 HTTP 401` when `AUTH-003 Expired JWT` is confirmed) so the primary root cause is ranked `#1`.

### Step 5 — Generate a Remediation Plan (`fix_generator.py:generate_remediation_plan`)
Produces structured `RemediationPlanItem` objects containing:
- **Level 1**: Problem, root cause, supporting evidence, risk level, and recommended solution.
- **Level 2**: Reviewable unified diff (`unified_diff`) validated against `validate_patch_safety()`.

### Step 6 — Apply Approved Changes (`fix_generator.py:apply_approved_fix`)
- **Level 3**: Applies repository or configuration patches **only** after explicit developer approval (`ApproveFixRequest(approved=True)`). Unapproved modification attempts raise `RepairApprovalRequiredError`.

### Step 7 — Verify (`verifier.py:verify_remediation`)
- **Level 4**: Re-runs the deterministic diagnostic suite (`run_diagnostic_verification`) after applying approved repairs, reporting `fix_worked`, `passed_checks`, `failed_checks`, `remaining_problems`, and `unverified_assumptions`.
