<!-- Parent: ../AGENTS.md -->

# streams — Public Stream Status

Worker/service health status (no authentication required).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/streams/status` | GET | List all workers' health from Redis (public endpoint) |

**Key Notes:**
- No JWT required — public monitoring endpoint
- Reads worker IDs from `epi:workers` set
- Fetches health data from `epi:worker:<id>:health` keys (JSON)
- Returns empty list if Redis unavailable
- Compatible with V1 API contract
