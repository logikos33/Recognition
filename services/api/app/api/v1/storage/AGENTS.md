<!-- Parent: ../AGENTS.md -->

# storage — R2/Local Storage Health & Testing

File storage connectivity checks and presigned URL generation.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/storage/health` | GET | Test R2 health (write/read/delete cycle) |
| `/api/v1/storage/test-upload` | POST | Upload test file, return download URL |

**Key Notes:**
- No JWT on health check (diagnostic endpoint)
- Health test performs write/read/delete on `_health_check/` prefix
- Test upload creates file in `test/` prefix
- Returns storage type (R2Storage, LocalStorage) + connection status
- Presigned URLs valid for 1 hour
