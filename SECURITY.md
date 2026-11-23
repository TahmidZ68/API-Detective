# Security Policy & Threat Model

Security and developer privacy are foundational requirements in **API Detective**.

## Supported Versions

| Version | Supported |
|---------|-----------|
| `0.1.x-alpha` | Yes |

## Threat Model & Implemented Defenses

### 1. Secret & Credential Exposure
- **Risk**: API debugging tools handle sensitive `Authorization` headers, Bearer tokens, JWTs, API keys, and query parameters that could leak into logs, SQLite/PostgreSQL storage, or exported reports.
- **Mitigation**:
  - `backend/app/core/security.py` enforces recursive secret redaction across headers (`redact_headers`), URLs (`redact_url`), structured payloads (`redact_object`), and free-form logs (`redact_text`).
  - JWT claim inspection (`AUTH-003`, `AUTH-007`) extracts only structural metadata (`alg`, `exp`, `nbf`, `scope`) in memory and never includes the raw JWT string in finding evidence.
  - Request body persistence is disabled by default (`PERSIST_REQUEST_BODIES=false`).

### 2. Server-Side Request Forgery (SSRF) & DNS Rebinding
- **Risk**: An API diagnostic service that makes outbound HTTP requests could be abused to probe cloud metadata services (`169.254.169.254`), internal private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), or localhost admin ports.
- **Mitigation**:
  - `validate_url_ssrf()` enforces `http`/`https` schemes only and blocks decimal integer, octal, and hex IP representations.
  - Cloud metadata hostnames and link-local IPs (`169.254.169.254`, `100.100.100.200`, `fd00:ec2::254`, `metadata.google.internal`) are unconditionally blocked.
  - Pre-flight DNS resolution is inspected before connection establishment to block domains resolving to loopback, link-local, multicast, CGNAT (`100.64.0.0/10`), IPv6-mapped IPv4 (`::ffff:127.0.0.1`), or private RFC 1918 addresses.
  - **Connection-Time Peer IP Verification**: `execute_diagnostic_request()` calls `_verify_connected_peer_ip(response)` to inspect the connected socket's `peername` IP address immediately upon response receipt and aborts with `SSRFProtectionError` if DNS rebinding resolved to a restricted peer IP.
  - **Local vs. Hosted Multi-User Deployment**: For a locally installed developer CLI/dashboard, pre-flight DNS checks + connection-time peer IP verification provide defense-in-depth. For any **hosted multi-user deployment**, operators **must** also enforce network-level egress firewall restrictions (Kubernetes `NetworkPolicy`, VPC egress security groups, or an egress proxy blocking RFC 1918, link-local, CGNAT, and IPv6 unique-local ranges) so TCP handshakes to internal hosts are blocked at the network boundary.
  - Redirects are capped (`MAX_REDIRECTS=3`) and every redirect hop is re-validated against SSRF rules before following.
  - Cross-origin redirects and `HTTPS -> HTTP` downgrade redirects automatically strip `Authorization`, `Proxy-Authorization`, `Cookie`, and `X-API-Key` headers.

### 3. Prompt Injection via Untrusted Specs or Repositories
- **Risk**: Malicious OpenAPI specifications, HTTP responses, or third-party repositories could embed prompt injection strings attempting to hijack an optional LLM provider.
- **Mitigation**:
  - Core diagnostics and tool execution are 100% deterministic Python functions (`ToolExecutor`) and cannot be altered by LLM output.
  - Repository code is never transmitted to an external LLM unless `ALLOW_REPO_TRANSMISSION_TO_LLM=true` is explicitly enabled.
  - Any untrusted text passed to optional LLM synthesis is sanitized and wrapped in `<untrusted_content>` boundary tags via `sanitize_untrusted_content()`.

### 4. Unsafe Automated Code Repairs
- **Risk**: Automated repair tools might weaken security (e.g., adding `verify=False` to bypass TLS errors) or silently overwrite developer files.
- **Mitigation**:
  - Repository inspection operates in read-only mode by default.
  - File modifications (`Repair Level 3`) require explicit developer approval (`RepairApprovalRequiredError`).
  - `validate_patch_safety()` rejects any unified diff that introduces `verify=False`, `rejectUnauthorized: false`, or `NODE_TLS_REJECT_UNAUTHORIZED=0` (`ForbiddenRepairError`).

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities. Report suspected vulnerabilities privately by emailing `security@apidetective.dev` with reproduction steps and affected components. We acknowledge reports within 48 hours.
