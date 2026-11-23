# API Detective — Public Alpha Release Readiness Tracker (`v0.1.0-alpha.2`)

**Release Classification:** Public Alpha — Experimental Software  
**Version:** `0.1.0-alpha.2`  
**License:** Apache License 2.0

---

## 1. Phase-by-Phase Readiness Matrix

| Phase | Milestone | Status | Artifact / Evidence |
|-------|-----------|--------|---------------------|
| **Phase A** | Complete Repository Audit | ✅ Completed | [docs/RELEASE_AUDIT.md](RELEASE_AUDIT.md) (`AUD-001`..`AUD-009` identified and resolved) |
| **Phase B** | Security Hardening (SSRF, Secrets, Repo, Agent, Repair) | ✅ Completed | [docs/SECURITY_AUDIT.md](SECURITY_AUDIT.md) (`SEC-01`..`SEC-06` remediated and tested) |
| **Phase C** | Agent Reliability Audit & Post-Fix Verification | ✅ Completed | [docs/AGENT_RELIABILITY.md](AGENT_RELIABILITY.md) (13 lifecycle checks verified) |
| **Phase D** | 25-Scenario + Independent Compound Benchmark Suite | ✅ Completed | [docs/BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) (`25/25` single-fault, `4/4` compound/boundary cases, methodology & semantic limits documented) |
| **Phase E** | Expanded Backend & Frontend Test Suites | ✅ Completed | `32 passed` in Pytest (`backend/tests/` + `tests/`), `10 passed` in Vitest (`frontend/tests/`) |
| **Phase F** | Developer Experience, CLI & Config Hardening | ✅ Completed | [`.env.example`](../.env.example), `--version` & `--help` verified across all 6 subcommands |
| **Phase G** | Frontend Release Polish & 9-Step Developer Journey | ✅ Completed | `frontend/src/` (7 views backed by real SQLite/PostgreSQL endpoints, E2E test passing) |
| **Phase H** | Open-Source Repository Metadata & Templates | ✅ Completed | [`.editorconfig`](../.editorconfig), `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md` |
| **Phase I** | README Redesign & Screenshot Documentation | ✅ Completed | [`README.md`](../README.md), [`docs/screenshots/README.md`](screenshots/README.md), [`docs/screenshots/cli_output.txt`](screenshots/cli_output.txt) |
| **Phase J** | GitHub Actions Workflows (`backend`, `frontend`, `security`, `release`) | ✅ Completed | `.github/workflows/backend-tests.yml`, `frontend-tests.yml`, `security.yml`, `release.yml` |
| **Phase K** | Agensi Skill Package Isolated Validation | ✅ Completed | [`API-Detective-Agensi-Skill.zip`](../API-Detective-Agensi-Skill.zip) extracted and executed in an isolated temp directory |
| **Phase L** | Versioning (`0.1.0-alpha.2`) & Changelog | ✅ Completed | [`pyproject.toml`](../pyproject.toml), [`CHANGELOG.md`](../CHANGELOG.md), `backend/app/__init__.py`, `frontend/package.json` |
| **Phase M** | Git Hygiene, Secret Scan, Commit & Local Tag | ✅ Completed | `git init`, secret scan (`0 leaks`), commit `release: prepare API Detective v0.1.0-alpha.2`, tag `v0.1.0-alpha.2` |

---

## 2. Final Acceptance Criteria Checklist

- [x] Repository audit is complete (`docs/RELEASE_AUDIT.md`).
- [x] Critical security findings are resolved (`docs/SECURITY_AUDIT.md`).
- [x] Agentic workflow is verified (`docs/AGENT_RELIABILITY.md`).
- [x] Diagnostic benchmark is reproducible (`docs/BENCHMARK_RESULTS.md`).
- [x] Backend tests pass (`29 passed`).
- [x] Frontend tests pass (`10 passed`).
- [x] Type checking passes (`mypy` 0 errors in 52 files; `tsc --noEmit` 0 errors).
- [x] Linting passes (`ruff check` 0 errors).
- [x] Production build succeeds (`vite build` succeeds cleanly).
- [x] CLI works in a clean environment (`api-detective --version` & all 6 commands).
- [x] Docker deployment configuration is validated (`Dockerfile`, `docker/Dockerfile.frontend`, `docker-compose.yml`).
- [x] README is complete (`README.md`).
- [x] Screenshots are real (`docs/screenshots/cli_output.txt`) or clearly marked as pending browser capture (`docs/screenshots/README.md`).
- [x] License is present (`LICENSE` — Apache License 2.0).
- [x] CI workflows are valid (`.github/workflows/*.yml`).
- [x] Security documentation is complete (`SECURITY.md`, `docs/SECURITY_AUDIT.md`).
- [x] Agensi skill ZIP is validated in an isolated temporary directory (`API-Detective-Agensi-Skill.zip`).
- [x] No secrets are present in the repository tree.
- [x] Git diff is reviewed.
- [x] Version information is consistent (`0.1.0-alpha.2`).
- [x] Known limitations are documented.

---

## 3. Pre-Push Final Verification Summary

| Pre-Push Checklist Item | Status | Evidence / Notes |
|-------------------------|--------|------------------|
| **1. Benchmark Independence & Methodology** | ✅ Verified | Added 4 compound & boundary cases (`C1`–`C4`) in [`tests/test_benchmark_suite.py`](../tests/test_benchmark_suite.py) and documented methodology & semantic business-logic boundaries in [`docs/BENCHMARK_RESULTS.md`](BENCHMARK_RESULTS.md). |
| **2. SSRF Connection-Time Peer IP & TOCTOU** | ✅ Verified | Implemented `_verify_connected_peer_ip()` in [`backend/app/tools/http_client.py`](../backend/app/tools/http_client.py), tested via `test_connection_time_peer_ip_toctou_protection`, and documented local vs. multi-user network egress requirements in [`SECURITY.md`](../SECURITY.md) & [`docs/SECURITY_AUDIT.md`](SECURITY_AUDIT.md). |
| **3. Concurrent Repair Rollback & Backup Cleanup** | ✅ Verified | Added per-file re-entrant locks (`_FILE_LOCKS`), investigation-scoped backup keys `(investigation_id, fix_id, file_path)`, bounded LRU capacity (`MAX_BACKUP_ENTRIES = 128`), and `cleanup_fix_backups()` in [`backend/app/agent/fix_generator.py`](../backend/app/agent/fix_generator.py), tested via `test_concurrent_investigation_repair_isolation_and_cleanup`. |
| **4. Complete Apache 2.0 LICENSE Text** | ✅ Verified | Verified [`LICENSE`](../LICENSE) contains the full official Apache License 2.0 terms (Sections 1–9), the official `APPENDIX: How to apply the Apache License to your work`, and the copyright notice. |
| **5. Clean Git History & Working Tree** | ✅ Verified | Verified via `git ls-tree -r HEAD --name-only` and `git log --stat` that no `.env`, `.db`, `.venv`, `node_modules`, or build caches exist in any commit in Git history. |
| **6. Docker Runtime & Live Browser Screenshots** | ⚠️ Host Dependent | `Docker version 29.7.2` is installed on the host, but the Windows execution sandbox blocks access to `npipe:////./pipe/docker_engine` (`Access is denied`). Run `docker compose up --build` and capture the 5 browser PNGs (`docs/screenshots/README.md`) in a normal host PowerShell session before or immediately after pushing. |
