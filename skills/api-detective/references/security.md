# Security, Privacy & Safe Repair Boundaries

## 1. Secret Redaction
- Sensitive headers (`Authorization`, `Proxy-Authorization`, `X-API-Key`, `API-Key`, `Cookie`, `Set-Cookie`, `X-Auth-Token`, `Client-Secret`) are masked as `***REDACTED***`.
- Inline token patterns (`Bearer ...`, `Basic ...`, `sk-...`, `ghp_...`, `AIza...`, and three-part JWTs `eyJ...`) are redacted across logs, error traces, URLs, and reports.

## 2. Network & SSRF Protections
- Only `http` and `https` schemes are permitted.
- Cloud metadata endpoints (`169.254.169.254`, `100.100.100.200`, `fd00:ec2::254`, `metadata.google.internal`) are unconditionally blocked.
- Private RFC 1918 networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) and loopback addresses (`127.0.0.1`, `::1`, `localhost`) are blocked by default unless `--allow-localhost` is explicitly passed for local debugging.
- Every redirect hop is re-validated against SSRF rules before following.

## 3. Forbidden Automated Repairs
API Detective enforces strict repair safety guards (`validate_patch_safety`) and will **never**:
- Disable SSL/TLS certificate verification (`verify=False` or `rejectUnauthorized: false`).
- Remove authentication middleware or weaken authorization checks.
- Overwrite source files without explicit developer approval (`Level 3`).
- Transmit repository code to external LLM providers without opt-in consent.
