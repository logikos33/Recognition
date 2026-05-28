<!-- Parent: ../AGENTS.md -->

# reports — Home Page Reports

Global reports aggregating all modules for home dashboard.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reports/home` | GET | Global reports for home page (all tenant modules) |

**Key Notes:**
- Aggregates metrics across all modules (EPI, PPE, safety, etc.)
- Scoped to tenant_id
- Includes: active alerts, detection trends, module stats
- Used by frontend home dashboard
