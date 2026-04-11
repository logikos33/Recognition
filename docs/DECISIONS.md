# Architecture Decision Records — EPI Monitor V2

This file logs key architectural decisions made for the EPI Monitor V2 project.
Decisions are append-only. Do not remove or alter past entries.

---

### ADR-001: psycopg2 direto, sem ORM

**Date**: 2024-01
**Status**: Accepted
**Context**: The project required database access for a multi-tenant Flask API with a schema under active development.
**Decision**: Use raw psycopg2 with RealDictCursor throughout. No SQLAlchemy, no ORM. All SQL lives in repository classes under `infrastructure/database/repositories/`.
**Reason**: Explicit control over queries, simpler debugging of production issues, and alignment with the team's SQL expertise. ORM abstraction layers were deemed unnecessary overhead for a team comfortable writing SQL directly.

---

### ADR-002: Multi-tenant desde dia 1

**Date**: 2024-01
**Status**: Accepted
**Context**: The system serves multiple companies (tenants) from a single deployment. Adding multi-tenancy after launch would require rewriting every query and migration.
**Decision**: Every table includes `tenant_id UUID REFERENCES tenants(id)`. The JWT payload carries a tenant claim. `get_tenant_id()` in `app/core/auth.py` extracts it. All queries filter by tenant_id without exception.
**Reason**: Retrofitting multi-tenancy into an existing schema is exponentially harder than building it in from the start. Strict enforcement at the repository layer prevents data leaks between tenants.

---

### ADR-003: Worker V1 deprecated, servicos separados

**Date**: 2024-06
**Status**: Accepted
**Context**: The original monolithic worker handled FFmpeg transcoding, YOLO inference, event publishing, and scheduling in a single process. This caused memory pressure, restart cascades when one component failed, and blocked independent scaling.
**Decision**: Split the monolith into independent services: `inference-service`, `scheduler-service`, and `training-service`. The legacy worker in `worker/` is marked DEPRECATED and will be removed once all traffic migrates.
**Reason**: Independent scaling per workload, isolation of heavy ML dependencies (torch, ultralytics) from the API process, and faster recovery when a single component crashes.

---

### ADR-004: Edge Agent outbound-only

**Date**: 2024-09
**Status**: Accepted
**Context**: Customer IP cameras sit behind NAT and corporate firewalls. Requiring inbound port forwarding (e.g., opening port 554 externally) is a deployment blocker for most enterprise customers.
**Decision**: Deploy a lightweight edge agent on the customer network that initiates all connections outbound over HTTPS/WSS on port 443. Supports three modes: relay (stream forwarded to cloud), edge inference (YOLO runs locally, only events sent), and hybrid (inference local, model updates from cloud).
**Reason**: Eliminates port forwarding requirements entirely. Port 443 outbound is open in virtually all corporate environments. Customers retain video data on-premises in edge inference mode.

---

### ADR-005: Migrations forward-only

**Date**: 2024-02
**Status**: Accepted
**Context**: The production database on Railway holds live customer data. A rollback migration that drops columns or tables could cause irreversible data loss.
**Decision**: All migration files use only `CREATE TABLE IF NOT EXISTS` and `ADD COLUMN IF NOT EXISTS`. No `DROP TABLE`, no `DROP COLUMN`, no down migrations. Migration files are numbered sequentially (`001_initial.sql` ... `NNN_name.sql`) and run automatically at API startup.
**Reason**: Production safety by design. If a migration is wrong, the fix is a new forward migration, not a rollback. This prevents accidental data loss from a misapplied down migration in a CI/CD pipeline.
