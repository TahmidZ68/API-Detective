# API Detective — Phase A Comprehensive Release Audit (`v0.1.0-alpha.1` → `v0.1.0-alpha.2`)

**Audit Date:** 2026-11-23  
**Audited Version:** `0.1.0-alpha.1`  
**Target Release Version:** `0.1.0-alpha.2` (Public Alpha — Experimental Software)

---

## 1. Existing Architecture Assessment

API Detective is organized into six decoupled layers:

1. **Core & Security (`backend/app/core/`)**: Settings (`config.py`), SSRF and secret redaction (`security.py`), structured JSON logging (`logging.py`), and domain exceptions (`exceptions.py`).
2. **Deterministic Diagnostic Engine (`backend/app/diagnostics/`)**: Six pure diagnostic analyzers (`connectivity.py`, `authentication.py`, `request_analyzer.py`, `schema_validator.py`, `response_analyzer.py`, `integration_analyzer.py`) producing standardized `DiagnosticFinding` models.
3. **Diagnostic & Repository Tools (`backend/app/tools/`)**: `http_client.py`, `openapi_parser.py`, `repository_inspector.py`, `log_analyzer.py`, and `test_runner.py`.
4. **7-Step Agent Engine (`backend/app/agent/`)**: Framework-agnostic orchestration (`orchestrator.py`, `planner.py`, `investigator.py`, `root_cause.py`, `fix_generator.py`, `verifier.py`) with optional LLM synthesis (`backend/app/providers/llm.py`).
5. **FastAPI REST API & SQLAlchemy Storage (`backend/app/api/`, `backend/app/services/`, `backend/app/models/`)**: Persistence for investigations, dashboard metrics, repair approvals, and JSON/Markdown/HTML exports.
6. **Interfaces & Distribution (`cli/`, `frontend/`, `skills/api-detective/`)**: Typer/Rich CLI, React 18 + TypeScript + Tailwind CSS dashboard, and Agensi skill package.

---

## 2. Verified Working Functionality

- **Deterministic Diagnostics**: All 6 diagnostic modules run without an LLM API key and return structured findings with evidence and confidence scores.
- **OpenAPI & JSON Schema Parsing**: Parses OpenAPI 3.0, 3.1, Swagger 2.0 (JSON/YAML), and JSON Schema with local `$ref` dereferencing.
- **CLI Commands**: `diagnose`, `inspect`, `validate`, `investigate`, `report`, and `config` execute independently of the web dashboard.
- **Web Dashboard**: All 7 pages render and communicate with the FastAPI backend via `/api/v1/*`; production Vite bundle builds cleanly.
- **Existing Test Suite**: 24 backend/integration Pytest tests and 6 frontend Vitest tests pass; Ruff and MyPy report 0 errors.

---

## 3. Incomplete Functionality & Release Blockers

| ID | Area | Severity | Finding |
|----|------|----------|---------|
| `AUD-001` | SSRF Protection (`security.py`) | **High** | `validate_url_ssrf` does not unwrap IPv6-mapped IPv4 addresses (e.g., `::ffff:127.0.0.1` or `::ffff:169.254.169.254`), nor does it block alternative numeric/octal/hex IP representations (`0177.0.0.1`, `0x7f000001`, integer `2130706433`) when DNS resolution is bypassed or mocked. |
| `AUD-002` | Redirect Security (`http_client.py`) | **High** | `execute_diagnostic_request` strips `Authorization` on cross-host redirects, but does not strip `Authorization` on same-host `HTTPS -> HTTP` protocol downgrade redirects before issuing the next hop. |
| `AUD-003` | Repository Security (`repository_inspector.py`) | **High** | `os.walk` does not reject symlinks or verify that resolved target files remain strictly inside the repository root (`is_relative_to`), and does not filter binary files containing null bytes (`\x00`). |
| `AUD-004` | Repair Verification (`verifier.py`, `fix_generator.py`) | **High** | `verify_remediation` does not re-run `inspect_repository()` after applying Level 3 repository repairs, and `apply_approved_fix` lacks automatic backup/rollback if a file modification or subsequent verification fails. |
| `AUD-005` | Agent Loop Bounds (`investigator.py`) | **Medium** | `ToolExecutor.execute_plan` computes `max_tool_steps = max(len(plan), self.max_iterations * 2)`, which allows `len(plan)` to override a strict `max_iterations` limit and does not track duplicate `(tool_name, context)` invocations. |
| `AUD-006` | Secret Redaction (`security.py`) | **Medium** | Inline secret patterns should be expanded to cover PEM private keys (`-----BEGIN ... PRIVATE KEY-----`), AWS access key IDs (`AKIA...`), Slack tokens (`xox...`), and sensitive cookie/header tokens. |
| `AUD-007` | CLI Version Flag (`cli/api_detective/main.py`) | **Low** | CLI lacks a top-level `--version` / `-V` callback flag for quick version verification in CI environments. |
| `AUD-008` | Benchmark Coverage (`tests/`) | **Medium** | Current integration suite tests 12 scenarios; Phase D requires a 25-scenario API benchmark plus synthetic multi-language repository benchmarks with precision/recall/false-positive reporting. |
| `AUD-009` | GitHub Repository Hygiene (`.github/`, Git) | **Medium** | Repository is not yet initialized with Git; `.editorconfig`, `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`, and split workflows (`backend-tests.yml`, `frontend-tests.yml`, `security.yml`, `release.yml`) are missing. |

---

## 4. Security Concerns Summary

1. **SSRF Alternative IP & IPv6-Mapped IPv4 Bypass (`AUD-001`)** — Must be fixed and covered by unit tests before public alpha.
2. **HTTPS-to-HTTP Downgrade Credential Leak (`AUD-002`)** — Must strip `Authorization` and `Cookie` headers on any protocol downgrade redirect.
3. **Symlink Escape in Repository Inspector (`AUD-003`)** — Must skip symlinks (`is_symlink()`) and enforce `resolved_path.is_relative_to(repo_root)`.
4. **Patch Backup & Rollback (`AUD-004`)** — Must snapshot original file contents before applying Level 3 edits and support rollback on error.

---

## 5. Test Coverage Gaps

- Missing unit tests for IPv6 loopback (`[::1]`), IPv6-mapped IPv4 (`[::ffff:127.0.0.1]`), octal/hex/integer IPs, and DNS rebinding via mocked `socket.getaddrinfo`.
- Missing unit tests for symlink escape rejection and binary file skipping in `inspect_repository`.
- Missing unit tests for prompt injection attempts embedded inside OpenAPI descriptions and repository comments.
- Missing 25-scenario quantitative benchmark runner comparing diagnostic engine detection vs. agent root-cause ranking.
- Missing frontend tests for `RequestInspectorPage`, `AgentSettingsPage`, and complete end-to-end user journey.

---

## 6. Dependency & Deployment Concerns

- **Python & Node Dependencies**: All dependencies use permissive open-source licenses (MIT, BSD, Apache-2.0) compatible with Apache License 2.0.
- **Frontend Lockfile**: Ensure `package-lock.json` or clean `npm install` compatibility is documented and workflows run deterministically.
- **SQLite Artifacts**: Local `api_detective.db` created during test runs must be cleaned and excluded via `.gitignore`.

---

## 7. Recommended Corrections Execution Plan

1. **Phase B**: Harden `security.py`, `http_client.py`, `repository_inspector.py`, and `fix_generator.py`; write `docs/SECURITY_AUDIT.md`.
2. **Phase C**: Fix iteration bounds, duplicate tool call prevention, competing hypothesis retention, and repository re-verification in `investigator.py` and `verifier.py`; write `docs/AGENT_RELIABILITY.md`.
3. **Phase D & E**: Implement the 25-scenario API + synthetic repository benchmark suite and expanded backend/frontend tests; generate `docs/BENCHMARK_RESULTS.md`.
4. **Phase F, G, H, I, J, K, L, M**: Add `--version` to CLI, expand `.env.example`, add GitHub templates and 4 CI workflows, rebuild and test `API-Detective-Agensi-Skill.zip` in an isolated temp folder, bump version to `0.1.0-alpha.2`, capture real screenshots, initialize Git, review diff, and tag `v0.1.0-alpha.2`.
