# API Detective — Security Audit & Verification Report (`v0.1.0-alpha.2`)

**Audit Scope:** `backend/app/core/security.py`, `backend/app/tools/http_client.py`, `backend/app/tools/repository_inspector.py`, `backend/app/agent/fix_generator.py`, `backend/app/providers/llm.py`

---

## 1. Threat Model

API Detective operates in developer environments where it inspects HTTP endpoints, OpenAPI specifications, error logs, and local source code repositories. The primary threat vectors are:

1. **Server-Side Request Forgery (SSRF) & DNS Rebinding**: Attackers or malicious specs supplying URLs targeting cloud instance metadata (`169.254.169.254`), internal RFC 1918 networks, IPv6 loopback (`[::1]`), IPv6-mapped IPv4 addresses (`[::ffff:127.0.0.1]`), or alternative IP encodings (`0177.0.0.1`, `0x7f000001`, integer `2130706433`), or redirecting an initial public URL to an internal target.
2. **Credential & Secret Leakage**: Sensitive headers (`Authorization`, `X-API-Key`, `Cookie`, `Private-Token`, `X-Gitlab-Token`), Bearer tokens, JWTs, PEM private keys, AWS keys (`AKIA...`), or query-string credentials leaking into logs, SQLite/PostgreSQL tables, or exported reports.
3. **Repository Path Traversal & Symlink Escape**: Malicious repositories containing symlinks pointing outside the repository root (e.g., `/etc/passwd` or `~/.ssh/id_rsa`) or oversized/binary payloads.
4. **Prompt Injection via Untrusted Inputs**: Malicious instructions embedded inside OpenAPI descriptions, server error payloads, or repository comments attempting to hijack optional LLM synthesis or trigger unauthorized repairs.
5. **Unsafe Automated Repairs**: Code patches attempting to disable TLS verification (`verify=False`, `rejectUnauthorized: false`), hardcode credentials, or modify files without explicit developer approval.

---

## 2. Security Findings & Applied Remediations

| ID | Category | Severity | Vulnerability Discovered in `v0.1.0-alpha.1` | Fix Implemented in `v0.1.0-alpha.2` | Verification Test |
|----|----------|----------|----------------------------------------------|-------------------------------------|-------------------|
| `SEC-01` | SSRF (`B1`) | **High** | IPv6-mapped IPv4 addresses (`::ffff:127.0.0.1`, `::ffff:169.254.169.254`) were evaluated only as IPv6 literals without unwrapping `ip.ipv4_mapped`. | Added `ip.ipv4_mapped` unwrapping in `_is_forbidden_ip()` and CGNAT (`100.64.0.0/10`) / reserved range checks. | `test_ssrf_advanced_ipv6_and_alternative_ips` |
| `SEC-02` | SSRF (`B1`) | **High** | Alternative numeric IP encodings (integer `2130706433`, hex `0x7f000001`, octal `0177.0.0.1`) were not rejected prior to socket connection. | Added `_is_obfuscated_ip_hostname()` in `validate_url_ssrf()` blocking decimal integer, octal, and hex IP representations. | `test_ssrf_advanced_ipv6_and_alternative_ips` |
| `SEC-03` | Redirect Security (`B1`) | **High** | `execute_diagnostic_request` stripped `Authorization` on cross-host redirects, but retained `Authorization` on same-host `HTTPS -> HTTP` downgrade redirects. | Updated `http_client.py` to strip `Authorization`, `Proxy-Authorization`, `Cookie`, and `X-API-Key` on any cross-origin redirect OR `HTTPS -> HTTP` protocol downgrade. | `test_redirect_downgrade_strips_authorization` |
| `SEC-04` | Secret Protection (`B2`) | **Medium** | Multi-line PEM private keys, AWS `AKIA` access keys, Slack `xox*` tokens, and URL-encoded query credential keys required broader redaction patterns. | Expanded `INLINE_SECRET_PATTERNS`, `SENSITIVE_HEADER_NAMES`, and URL-unquoted query key matching in `security.py`. | `test_deep_secret_redaction_formats` |
| `SEC-05` | Repository Security (`B3`) | **High** | `inspect_repository()` did not check `is_symlink()` or filter binary files containing null bytes (`\x00`). | Added `is_symlink()`, `_is_within_root()`, `_is_binary_file()`, and hardcoded secret detection (`HARDCODED_SECRET_RE`) in `repository_inspector.py`. | `test_repository_symlink_and_binary_protection` |
| `SEC-06` | Agent & Repair Security (`B4/B5`) | **High** | `apply_approved_fix()` lacked transactional backup and rollback if a multi-file patch failed or needed reversion. | Added `_FILE_BACKUP_REGISTRY`, transactional rollback on exception, and `rollback_approved_fix()` in `fix_generator.py`. | `test_repair_backup_and_rollback` |

---

## 3. Reproduction & Verification Steps

Run the dedicated security test suite offline:

```bash
python -m pytest backend/tests/test_security_and_agent.py -v
```

### Verified Assertions:
- `validate_url_ssrf("http://[::ffff:169.254.169.254]/latest/meta-data")` raises `SSRFProtectionError`.
- `validate_url_ssrf("http://[::1]:8000/admin")` raises `SSRFProtectionError`.
- `validate_url_ssrf("http://0177.0.0.1/")`, `validate_url_ssrf("http://0x7f000001/")`, and `validate_url_ssrf("http://2130706433/")` raise `SSRFProtectionError`.
- Mocked DNS rebinding (`evil.example.com -> 127.0.0.1` or `169.254.169.254`) raises `SSRFProtectionError` inside `execute_diagnostic_request()`.
- Redirect hop to `http://169.254.169.254/` mid-chain raises `SSRFProtectionError`.
- Same-host `https://secure.example.com/v1 -> http://secure.example.com/v1` redirect strips `Authorization` before the second hop.
- Symlinked files pointing outside `repo_root` are ignored during `inspect_repository()` and blocked by `apply_approved_fix()`.

---

## 4. Remaining Limitations & Hosted Multi-User Guidance

1. **DNS Rebinding & Connection-Time Peer IP Verification**:
   - **Implemented Application Control**: In addition to pre-flight DNS resolution checks (`validate_url_ssrf`), `execute_diagnostic_request()` in `backend/app/tools/http_client.py` calls `_verify_connected_peer_ip(response)` to inspect the connected socket's `peername` IP address (`network_stream.get_extra_info("peername")`) immediately upon response receipt and aborts with `SSRFProtectionError` if the peer IP is loopback, link-local, metadata, CGNAT, or RFC 1918 private.
   - **Local vs. Hosted Multi-User Deployment**: While pre-flight DNS validation + post-connect peer IP verification catches DNS rebinding before response bodies or redirects are processed, the TCP handshake itself occurs at the OS socket layer. For a locally installed single-developer CLI/dashboard tool, this application-layer guard is sufficient. For any **hosted multi-user deployment**, operators **must** pair `BLOCK_PRIVATE_NETWORKS=true` with network-level egress firewall rules (e.g., Kubernetes `NetworkPolicy`, VPC egress security groups, or an egress proxy blocking `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `100.64.0.0/10`, and `fc00::/7`).
2. **Custom Proprietary Token Formats**: Tokens that do not use standard sensitive key/header names or recognizable prefixes (`Bearer`, `Basic`, `sk-`, `ghp_`, `AKIA`, `AIza`, `xox`, `eyJ`) should be passed via redactable headers (`Authorization` or `X-API-Key`).
