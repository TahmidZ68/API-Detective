# Self-Hosting & Production Deployment Guide

API Detective is designed for straightforward self-hosting via Docker Compose, standalone Python virtual environments, or PostgreSQL-backed Kubernetes/container deployments.

---

## 1. Quick Start with Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
```

- **Backend REST API & OpenAPI Docs**: `http://localhost:8000/docs`
- **Health Check Endpoint**: `http://localhost:8000/api/v1/health`
- **Web Dashboard**: `http://localhost:5173`

---

## 2. Production PostgreSQL Configuration

By default, API Detective uses SQLite (`sqlite:///./api_detective.db`) for zero-config local development. For production deployments, configure `DATABASE_URL` in `.env`:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://detective_user:strong_password@db.internal:5432/api_detective
BLOCK_PRIVATE_NETWORKS=true
ALLOW_LOCALHOST_TARGETS=false
REDACT_SECRETS=true
PERSIST_REQUEST_BODIES=false
```

---

## 3. Security Hardening Recommendations

1. **Keep `BLOCK_PRIVATE_NETWORKS=true` and `ALLOW_LOCALHOST_TARGETS=false`** in any shared or multi-user hosted environment so users cannot probe internal RFC 1918 subnets or loopback services.
2. **Keep `PERSIST_REQUEST_BODIES=false`** when diagnosing endpoints that process PII or regulated payloads.
3. **Keep `ALLOW_REPO_TRANSMISSION_TO_LLM=false`** unless an organization-approved LLM gateway is configured via `LLM_BASE_URL`.
