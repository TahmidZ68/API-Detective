# API Detective Product Roadmap

## Completed in `v0.1.0-alpha.2` (Public Alpha — Experimental Software)
- [x] Phase 1: Foundation (FastAPI backend, Pydantic v2 schemas, SQLAlchemy persistence, structured logging, CI workflows)
- [x] Phase 2: Deterministic Diagnostic Engine (Connectivity, Authentication, Request, Schema, Response, Integration modules)
- [x] Phase 3: CLI Experience (Typer & Rich terminal reporting, `--version`, JSON output, CI exit codes)
- [x] Phase 4: Agent Engine (7-step investigation lifecycle, optional LLM provider adapter for OpenAI/Gemini/Anthropic/Local)
- [x] Phase 5: Repository Intelligence (Read-only scanner for Python, JavaScript, TypeScript, and `.env` files with symlink & binary guards)
- [x] Phase 6: Safe Repair & Verification (4-level repair workflow, unified diffs, explicit approval gate, transactional rollback, forbidden-patch guard)
- [x] Phase 7: Web Dashboard (React, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts)
- [x] Phase 8: Agensi Skill Package (`skills/api-detective/` and isolated-validated `API-Detective-Agensi-Skill.zip`)
- [x] Phase 9: Security Hardening & 25-Scenario Real-World Benchmark Suite (`docs/SECURITY_AUDIT.md`, `docs/BENCHMARK_RESULTS.md`)
- [x] Phase 10: GitHub Public Alpha Release Readiness (`docs/RELEASE_AUDIT.md`, `docs/AGENT_RELIABILITY.md`, `docs/RELEASE_READINESS.md`)

## Post-Alpha External Validation Targets (Before Starting `v0.2.0`)

Before introducing new `v0.2.0` protocol expansions, the immediate milestone is real-world validation with external developers. The table below defines **target validation goals** (not claimed results):

| Validation Metric | Initial Target |
|-------------------|----------------|
| Independent external developer testers | `10` |
| Real-world API debugging scenarios collected | `30` |
| Verified clean-machine installations | `10` |
| Verified end-to-end repair & rollback scenarios | `10` |
| Unresolved critical security vulnerabilities | `0` |

## Planned for `v0.2.0` (Beta)
- [ ] GraphQL and gRPC/Protobuf diagnostic analyzers
- [ ] HAR (HTTP Archive) and cURL command import in CLI and Web Dashboard
- [ ] AST-based multi-file refactoring patches for Python and TypeScript SDKs
- [ ] Alembic automated schema migration scripts for multi-tenant PostgreSQL deployments
- [ ] Pre-commit hook plugin for validating OpenAPI contracts against repository client calls in CI
