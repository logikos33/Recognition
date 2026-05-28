<!-- Parent: ../AGENTS.md -->

# modules — Multi-Tenant Module Management

List and manage EPI modules per tenant.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/modules/` | GET | List all modules for tenant with stats |
| `/api/modules/<code>` | GET | Get module details (code, name, description) |
| `/api/modules/<code>/classes` | GET | Get YOLO classes for module |
| `/api/modules/<code>/stats` | GET | Get stats (cameras, alerts, etc.) for module + tenant |

**Key Notes:**
- All operations scoped to tenant_id
- Module code examples: `epi`, `ppe`, `safety`
- Stats include total alerts, active cameras, violations by class
- Access control: 403 if tenant doesn't have module
