# Audit Report — EPI Monitor V2

**Date**: 2026-04-10
**Branch**: rescue/governance-infra (based on baguncinha, 125 commits ahead of main)
**Auditor**: Claude Code + Vitor Emanuel

---

## Summary

| Metric | Value |
|--------|-------|
| Backend Python files | ~128 |
| Frontend TS/TSX files | ~101 |
| Total migrations | 13 (001-013) |
| Test modules | 27 (unit + integration) |
| Tests passing | 87 |
| Railway services | 13 |
| Architecture | DDD (core/domain/infrastructure/api) |
| Circular imports | 0 |
| Dead imports (pre-fix) | 3 (worker/worker_server.py) |

**Health Score: 7/10** — Solid architecture and test coverage, but accumulated debris from V1->V2 migration needed cleanup.

---

## Issues Found and Resolved

### Fixed in This Audit

| Issue | Severity | Resolution |
|-------|----------|------------|
| `worker/worker_server.py` — 3 dead imports from nonexistent `services.shared.events`, `api.utils.stream_manager`, `api.utils.yolo_processor` | CRITICAL | Wrapped with try/except stubs matching existing pattern |
| `backend/app/api/v1/annotations/` — Empty module (only `__init__.py`), not registered as blueprint | LOW | Deleted |
| `backend/app/api/v1/datasets/` — Empty module (only `__init__.py`), not registered as blueprint | LOW | Deleted |
| `services/` directory — Ghost dir with only `__init__.py` + AGENTS.md, no real code | MEDIUM | Deleted |
| CLAUDE.md referenced `services/shared/events.py` and `services/shared/database.py` | MEDIUM | Removed stale references, pointed to actual `app/core/socket_bridge.py` |
| Home-level `~/CLAUDE.md` referenced `.claude/agents/*.md` files that don't exist | LOW | Removed file path column from agents table |

---

## Architecture Health

### Backend
- **Status**: Healthy
- Clean DDD layering: `core/` -> `domain/` -> `infrastructure/` -> `api/`
- No circular imports detected
- All models are frozen dataclasses (immutable)
- Parameterized SQL queries throughout (no SQL injection risk)
- Exception hierarchy with proper HTTP status codes
- DatabasePool singleton with ThreadedConnectionPool

### Frontend
- **Status**: Healthy
- React 18 + Vite 6 + TypeScript strict mode
- Zustand for state management (persisted)
- Custom fetch wrapper with 15s timeout and auto token injection
- socket.io-client for real-time WebSocket events
- Vanilla Extract for type-safe CSS

### Infrastructure
- **Status**: Healthy with deprecation debt
- 13 Railway services configured
- Nixpacks builds (2-3 min)
- Migration runner is idempotent with `schema_migrations` tracking
- `railway_start.py` handles routing by SERVICE_TYPE

### Worker (Legacy)
- **Status**: Deprecated
- `worker/DEPRECATED.md` documents planned removal in v3.0
- Replaced by: inference-service, scheduler-service, training-service
- Dead imports now wrapped with stubs (won't crash on startup)

---

## Technical Debt Inventory

| Item | Priority | Effort | Notes |
|------|----------|--------|-------|
| Remove `worker/` directory entirely | P2 | Low | Blocked on confirming no Railway service routes to it |
| Home-level `~/CLAUDE.md` is V1 documentation | P3 | Medium | Describes monolithic api_server.py, SQLAlchemy, Next.js 14 — all V1 |
| No down migrations | P3 | N/A | By design (ADR-005). Document, don't fix |
| InferenceService placeholder (54 lines) | P2 | Medium | Actual inference in Celery tasks, service is stub |
| ReportService minimal (78 lines) | P2 | Medium | Mostly stub endpoints |
| No rate limiting middleware | P2 | Low | Redis available, flask-limiter in deps |
| No request ID tracking | P3 | Low | Useful for debugging distributed requests |
| Camera password encryption key management | P2 | Low | Fernet key from env var, consider rotation strategy |

---

## Governance Infrastructure Added

| File | Purpose |
|------|---------|
| `.claude/commands/audit.md` | `/audit` slash command — quick health check |
| `.claude/commands/fix-bug.md` | `/fix-bug` slash command — structured bug fix workflow |
| `.claude/commands/new-migration.md` | `/new-migration` slash command — safe migration protocol |
| `.claude/commands/review.md` | `/review` slash command — compliance review |
| `docs/DATABASE.md` | Schema reference (single source of truth) |
| `docs/DECISIONS.md` | Architecture Decision Record log |
| `docs/AUDIT_REPORT.md` | This file |
| `CLAUDE.md` (updated) | Added: Migration Protocol, Impact Classification, Session Protocol |

---

## Recommendations

1. **Run `/audit` weekly** to catch regressions early
2. **Use `/new-migration` for ALL schema changes** — never create migrations ad-hoc
3. **Update `docs/DATABASE.md`** after every migration
4. **Append to `docs/DECISIONS.md`** when making architectural choices
5. **Consider removing `worker/`** entirely once confirmed no Railway service depends on it
6. **Add rate limiting** to public-facing endpoints (flask-limiter already in deps)
7. **Merge `rescue/governance-infra` to `baguncinha`** then to `staging` for deployment
