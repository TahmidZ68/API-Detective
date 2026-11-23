## Summary

<!-- Describe what this pull request changes and why. -->

## Related Issue

<!-- Link any related issue, e.g. Closes #123 -->

## Type of Change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New diagnostic rule (`CONN-*`, `AUTH-*`, `REQ-*`, `SCH-*`, `RES-*`, `INT-*`)
- [ ] Security hardening (SSRF, secret redaction, repository sandboxing, repair safety)
- [ ] CLI or Web Dashboard improvement
- [ ] Documentation / Benchmark update

## Verification & Quality Gates

- [ ] `pytest backend/tests tests -v` passes locally with 0 failures
- [ ] `ruff check backend cli skills tests` passes with 0 errors
- [ ] `mypy backend cli` passes with 0 errors
- [ ] `cd frontend && npm run typecheck && npm test && npm run build` succeeds
- [ ] No secrets, tokens, or `.env` files are included in this diff
- [ ] Deterministic engine works without an LLM API key (`LLM_PROVIDER=none`)
