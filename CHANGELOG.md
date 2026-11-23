# Changelog

All notable changes to **API Detective** are documented in this file.

## [0.1.0-alpha.2] - 2026-11-23 (Public Alpha — Experimental Software)

### Security Hardening
- **SSRF Protection (`backend/app/core/security.py`)**: Unwrapped IPv6-mapped IPv4 addresses (`::ffff:127.0.0.1`, `::ffff:169.254.169.254`), blocked alternative decimal integer (`2130706433`), octal (`0177.0.0.1`), and hexadecimal (`0x7f000001`) IP representations, and blocked CGNAT (`100.64.0.0/10`) and reserved IP ranges.
- **Redirect Credential Stripping (`backend/app/tools/http_client.py`)**: Stripped `Authorization`, `Proxy-Authorization`, `Cookie`, and `X-API-Key` headers on same-host `HTTPS -> HTTP` protocol downgrade redirects in addition to cross-origin redirects.
- **Expanded Secret Redaction (`backend/app/core/security.py`)**: Added inline redaction for PEM private keys (`-----BEGIN ... PRIVATE KEY-----`), AWS access key IDs (`AKIA...`), Slack tokens (`xox*`), GitLab/Stripe tokens, and URL-encoded sensitive query parameters.
- **Repository Sandboxing (`backend/app/tools/repository_inspector.py`)**: Added symlink rejection (`is_symlink()`), strict root boundary containment (`_is_within_root()`), binary file null-byte filtering (`_is_binary_file()`), and hardcoded credential detection (`INT-007`).
- **Transactional Patch Backup, Concurrency Locking & LRU Cleanup (`backend/app/agent/fix_generator.py`)**: Added per-file re-entrant locks (`_FILE_LOCKS`), investigation-scoped backup keys `(investigation_id, fix_id, file_path)` to prevent concurrent fix ID collisions, bounded LRU eviction (`MAX_BACKUP_ENTRIES = 128`), automatic backup removal upon rollback, and `cleanup_fix_backups()`.
- **Connection-Time Peer IP Verification (`backend/app/tools/http_client.py`)**: Added `_verify_connected_peer_ip()` to validate the connected socket's peer IP address against SSRF policies immediately upon response receipt, mitigating DNS TOCTOU rebinding alongside documented multi-user network egress requirements.

### Agent Reliability & Verification
- **Post-Fix Repository Re-Inspection (`backend/app/agent/verifier.py`, `backend/app/tools/test_runner.py`)**: Updated Step 7 verification to re-run `inspect_repository()` after applying Level 3 source code modifications and compare resolved `(diagnostic_id, title)` tuples accurately.
- **Strict Iteration & Duplicate Call Guards (`backend/app/agent/investigator.py`)**: Enforced strict `self.max_iterations` caps and added `executed_signatures` deduplication to prevent redundant identical tool invocations.

### Testing, Benchmarks & Developer Experience
- **25-Scenario Real-World Benchmark Suite (`tests/test_benchmark_suite.py`, `docs/BENCHMARK_RESULTS.md`)**: Added 25 API failure scenarios and multi-language synthetic repository benchmarks achieving `25/25 (100%)` engine detection and `25/25 (100%)` primary root-cause ranking with `0` false positives.
- **Expanded Frontend Test Suite (`frontend/tests/dashboard.test.tsx`)**: Expanded Vitest coverage from 6 to 10 tests covering all 7 dashboard views and the 9-step primary developer journey.
- **CLI Version Flag (`cli/api_detective/main.py`)**: Added `--version` / `-V` flag and verified `--help` across all subcommands.
- **GitHub Open-Source Release Infrastructure (`.github/`, `.editorconfig`)**: Added split CI workflows (`backend-tests.yml`, `frontend-tests.yml`, `security.yml`, `release.yml`), issue templates (`bug_report.yml`, `feature_request.yml`), `PULL_REQUEST_TEMPLATE.md`, `docs/RELEASE_AUDIT.md`, `docs/SECURITY_AUDIT.md`, `docs/AGENT_RELIABILITY.md`, and `docs/RELEASE_READINESS.md`.

---

## [0.1.0-alpha.1] - 2026-11-23

### Added
- **Deterministic Diagnostic Engine**: Implemented 43 diagnostic checks across Connectivity (`CONN-001`..`008`), Authentication (`AUTH-001`..`008`), Request Analysis (`REQ-001`..`008`), Schema Validation (`SCH-001`..`006`), Response Analysis (`RES-001`..`008`), and Integration Analysis (`INT-001`..`007`).
- **7-Step Agentic Investigation Engine**: Added framework-agnostic `AgentOrchestrator`, dynamic `build_investigation_plan`, bounded `ToolExecutor`, evidence-based `rank_root_causes`, 4-level repair `fix_generator`, and post-fix `verifier`.
- **OpenAPI & JSON Schema Intelligence**: Added parser and contract matcher supporting OpenAPI 3.0, OpenAPI 3.1, Swagger 2.0 (JSON/YAML), and standalone JSON Schema with local `$ref` dereferencing.
- **Repository-Aware Debugging**: Added read-only static inspection for Python (`requests`, `httpx`), JavaScript, TypeScript (`axios`, `fetch`), and `.env` files.
- **Typer & Rich CLI**: Added `diagnose`, `inspect`, `validate`, `investigate`, `report`, and `config` commands with CI/CD exit codes.
- **React + TypeScript Web Dashboard**: Built 7-page dark-first interface (Overview Dashboard, New Investigation, Investigation Workspace, Request Inspector, Diagnostic Reports, Agent Settings, and Documentation).
- **Agensi Skill Package**: Created `skills/api-detective/` with `SKILL.md`, 5 reference guides, 3 standalone scripts, and distributable `API-Detective-Agensi-Skill.zip`.
