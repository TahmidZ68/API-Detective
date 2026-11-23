# Contributing to API Detective

Thank you for your interest in contributing to **API Detective**! We build an open-source, deterministic-first API debugging and repair toolkit that developers can trust.

## Core Engineering Principles

1. **Deterministic Evidence Over Speculation**: Every diagnostic finding must include concrete evidence (`status`, `confidence`, and `evidence` array). Never fabricate diagnostic outputs or tool calls.
2. **LLM Functionality Is Strictly Optional**: All core diagnostics, root-cause ranking, unified diff generation, CLI commands, and dashboard workflows must work when `LLM_PROVIDER=none`.
3. **Security & Privacy First**: Never weaken SSRF checks, never log raw credentials, and never generate automated repairs that disable TLS (`verify=False`) or strip authentication.
4. **Tests Alongside Code**: Every new diagnostic rule (`CONN-*`, `AUTH-*`, `REQ-*`, `SCH-*`, `RES-*`, `INT-*`) must include unit and integration tests.

## Local Development Setup

### 1. Backend & CLI

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run backend tests, Ruff linter, and MyPy type checking:

```bash
pytest backend/tests tests -v
ruff check backend cli skills tests
mypy backend cli
```

### 2. Frontend Web Dashboard

```bash
cd frontend
npm install
npm run typecheck
npm test
npm run build
```

## Pull Request Checklist

- [ ] `pytest backend/tests tests` passes with 0 failures.
- [ ] `ruff check backend cli skills tests` passes with 0 errors.
- [ ] `mypy backend cli` passes with 0 errors.
- [ ] `npm run typecheck`, `npm test`, and `npm run build` succeed in `frontend/`.
- [ ] Documentation (`README.md`, `docs/API_REFERENCE.md`, and `skills/api-detective/references/`) is updated if new diagnostic IDs or endpoints were added.
