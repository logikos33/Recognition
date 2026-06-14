<!-- Parent: ../AGENTS.md -->

# health — System Health Checks

Database and Redis connectivity checks for Railway healthcheck.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (also at `/api/v1/health`) |

**Key Notes:**
- No JWT required — used by Railway healthcheck
- Returns 200 if DB OK (even if Redis degraded)
- Returns 503 if database unavailable
- Checks: database (SELECT 1), redis (PING)
- Never exposes connection strings or internal details
