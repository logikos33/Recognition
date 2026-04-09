<!-- Parent: ../AGENTS.md -->

# rules — Alert Rules Engine

CRUD for alert rules with duration/occurrence conditions.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rules` | GET | List all rules for tenant |
| `/api/rules` | POST | Create rule (violation_type + min_duration_seconds OR min_occurrences) |
| `/api/rules/<id>` | GET/PUT/DELETE | Read, update, delete rule |
| `/api/rules/<id>/toggle` | POST | Toggle enabled flag |

**Key Notes:**
- All rules scoped to tenant_id (multi-tenant)
- Required: `violation_type` + at least one of (`min_duration_seconds`, `min_occurrences`)
- Optional fields: `camera_id` (null = all), `time_window_seconds`, `create_alert` (default true)
- Toggle updates `enabled` flag and `updated_at` timestamp
