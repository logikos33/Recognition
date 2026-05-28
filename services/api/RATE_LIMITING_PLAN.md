# Rate Limiting Implementation Plan — EPI Monitor V2 Backend

**Date:** 2026-04-10  
**Status:** PLAN (Ready for execution)  
**Scope:** Add production-grade rate limiting to Flask API

---

## Current State Analysis

### Key Findings:
1. **No Rate Limiting Exists**: grep found 0 matches for `flask.limiter|flask-limiter|Limiter`
2. **Flask-Limiter Not in Dependencies**: Not in `requirements.txt`, `requirements-full.txt`, or `requirements-dev.txt`
3. **Redis Already Available**: REDIS_URL configured in `config.py` (lines 28-29)
4. **Extensions Pattern Established**: `app/extensions.py` uses lazy initialization pattern (lines 11-12)
5. **Middleware Registration Ready**: `app/__init__.py` has `register_*` functions (lines 16-81)
6. **No Request ID Tracking**: No existing tracking mechanism found

### Architecture Compatible:
- Flask app factory pattern in place
- Extension system already using lazy init
- Middleware registration system ready
- Redis connection pool available
- Error handlers and response patterns defined

---

## Implementation Checklist

### Phase 1: Dependencies
- [ ] Add `flask-limiter>=4.0.0,<5.0` to `requirements.txt`
- [ ] Add version constraint for redis backend (`limits>=3.8.0,<4.0` if needed)

### Phase 2: Core Limiter Setup
- [ ] Create `app/core/rate_limiting.py` with:
  - `RateLimiter` wrapper instance
  - `redis_storage` configuration (uses app.config['REDIS_URL'])
  - `get_identifier()` function (uses JWT user_id or IP)
  - Global limiter initialized in `extensions.py`

### Phase 3: Limiter Registration
- [ ] Update `app/extensions.py`:
  - Import limiter from core.rate_limiting
  - Export limiter for use in routes
- [ ] Update `app/__init__.py` create_app():
  - Call `limiter.init_app(app, ...)` after other extensions
  - Pass REDIS_URL to limiter if available, fallback to memory storage

### Phase 4: Route Decorators
Apply `@limiter.limit()` to public endpoints:

**Authentication Routes** (`app/api/v1/auth/routes.py`):
- `/register` → "5 per day" + "2 per minute" (signup spam prevention)
- `/login` → "10 per minute per IP" (brute-force protection)
- `/me` → No limit (authenticated)

**Video Upload** (`app/api/v1/videos/routes.py`):
- `/upload` → "10 per hour per user" (large file uploads)
- `/upload-url` → "50 per hour per user" (presigned URLs)
- `/extract` → "20 per hour per user"

**Cameras** (`app/api/v1/cameras/routes.py`):
- GET endpoints → "60 per minute per user"
- POST/PUT endpoints → "10 per minute per user"
- Test endpoint → "5 per minute per user" (RTSP expensive)

**Training** (`app/api/v1/training/routes.py`):
- Job creation → "20 per day per user"
- Annotation endpoints → "100 per minute per user"

**Other Endpoints**:
- Storage health → "60 per minute per IP"
- Health → No limit (system monitoring)
- Dashboard → "30 per minute per user"
- Reports → "20 per hour per user"

### Phase 5: Error Handling
- [ ] Add 429 handler in `app/core/middleware.py`:
  ```
  @app.errorhandler(429)
  def handle_rate_limit(e):
      return error("Rate limit exceeded. Try again later.", 429)
  ```

### Phase 6: Request ID Tracking (Optional Enhancement)
- [ ] Create `app/core/request_id.py`:
  - Generate UUID per request
  - Store in `request.request_id`
  - Include in log context
- [ ] Update middleware logging to include request_id
- [ ] Add request_id to error responses

### Phase 7: Configuration
- [ ] Add to `app/config.py`:
  ```python
  RATELIMIT_ENABLED: bool = not TESTING
  RATELIMIT_STORAGE_URL: str = REDIS_URL or None
  RATELIMIT_DEFAULT_LIMITS: list[str] = ["200 per day", "50 per hour"]
  RATELIMIT_STRATEGY: str = "fixed-window"
  ```

---

## File Changes Summary

### New Files:
1. `/backend/app/core/rate_limiting.py` (~80 lines)
2. `/backend/app/core/request_id.py` (~40 lines, optional)

### Modified Files:
1. `/backend/requirements.txt` — Add flask-limiter
2. `/backend/app/extensions.py` — Import/export limiter
3. `/backend/app/__init__.py` — Initialize limiter in create_app()
4. `/backend/app/core/middleware.py` — Add 429 handler + optional request_id
5. `/backend/app/config.py` — Add rate limit config vars (optional)
6. `/backend/app/api/v1/auth/routes.py` — Add decorators
7. `/backend/app/api/v1/videos/routes.py` — Add decorators
8. `/backend/app/api/v1/cameras/routes.py` — Add decorators
9. `/backend/app/api/v1/training/routes.py` — Add decorators
10. `/backend/app/api/v1/dashboard/routes.py` — Add decorators
11. `/backend/app/api/v1/storage/routes.py` — Add decorators
12. `/backend/app/api/v1/alerts/routes.py` — Add decorators
13. `/backend/app/api/v1/reports/routes.py` — Add decorators

### No Changes Needed:
- `app/__init__.py` — Already has extension registration pattern
- `app/core/exceptions.py` — Already handles custom errors
- `app/core/responses.py` — Already has error response format

---

## Implementation Strategy

### Step-by-Step Execution:

1. **Dependencies** (1 file, 1 line change)
   - Add flask-limiter to requirements.txt

2. **Core Setup** (2 new files)
   - Create rate_limiting.py
   - Create request_id.py (optional)

3. **Extension Registration** (2 files)
   - Update extensions.py to export limiter
   - Update __init__.py to initialize limiter

4. **Middleware** (1 file)
   - Add 429 handler
   - Add request_id injection (optional)

5. **Route Decorators** (8 route files)
   - Apply @limiter.limit() decorators
   - Most decorators on public endpoints only

6. **Configuration** (1 file, optional)
   - Add rate limit config to config.py

---

## Rate Limiting Strategy Details

### Storage Backend:
- **Production**: Redis (via REDIS_URL in config)
- **Development/Testing**: In-memory fallback
- **Rationale**: Redis already required for SocketIO and message queue

### Identifier Strategy:
```python
def get_identifier():
    # If JWT token present → use user_id (rate limit per user)
    # Else → use IP (rate limit per IP for public endpoints)
```

### Limits by Endpoint Type:

| Type | Limit | Rationale |
|------|-------|-----------|
| Register | 5/day, 2/min | Prevent signup spam |
| Login | 10/min/IP | Brute-force protection |
| File Upload | 10/hour | Large bandwidth consumer |
| Camera Test | 5/min | RTSP stream expensive |
| Job Creation | 20/day | Resource intensive |
| Read-only | 60/min | No resource impact |
| Health Check | Unlimited | System monitoring |

### Graceful Degradation:
- If Redis unavailable → Falls back to in-memory storage
- If limiter disabled (TESTING=True) → No limits applied
- Errors are caught and logged, not fatal

---

## Testing Strategy

### Unit Tests:
- Mock redis_storage
- Test identifier resolution (JWT vs IP)
- Test limit enforcement on single request

### Integration Tests:
- Test rate limit headers (X-RateLimit-*)
- Test 429 responses
- Test request_id propagation (if implemented)

### Manual Testing:
```bash
# Test login rate limit
for i in {1..12}; do curl -X POST http://localhost:5000/api/auth/login; done
# Should get 429 on request 11+

# Test with valid user (authenticated)
curl -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/v1/cameras
# Should allow up to 60/minute
```

---

## Rollback Plan

If issues arise:
1. Remove `@limiter.limit()` decorators
2. Comment out `limiter.init_app()` in `__init__.py`
3. Keep rate_limiting.py and redis setup (no harm)
4. Restart app

---

## Success Criteria

- [ ] 429 responses returned when limits exceeded
- [ ] Rate limit headers present in responses
- [ ] No performance degradation (Redis latency ~1-5ms)
- [ ] Tests pass (60% coverage maintained)
- [ ] Public endpoints protected, authenticated endpoints graceful
- [ ] Request ID tracked in logs (if implemented)
- [ ] Redis fallback works if Redis unavailable

---

## Notes & Assumptions

1. **Flask-Limiter Version**: Using 4.x (stable, supports Redis)
2. **Redis**: Already available in production (Railway service)
3. **Testing Mode**: Limiter disabled (TESTING=True)
4. **Request ID**: Optional enhancement, can be added later
5. **Backward Compatibility**: No breaking changes to API responses (429 is standard HTTP)
6. **Configuration**: Environment-driven, no hardcoded values

---

## Timeline

- **Phase 1 (Dependencies)**: 5 min
- **Phase 2 (Core Setup)**: 15 min
- **Phase 3 (Registration)**: 10 min
- **Phase 4 (Decorators)**: 20 min
- **Phase 5 (Error Handler)**: 5 min
- **Phase 6 (Request ID)**: 10 min (optional)
- **Phase 7 (Config)**: 5 min (optional)

**Total**: ~70 min (60 min core + 10 min optional)

---

## Ready for Execution

All information gathered:
- File locations confirmed
- Current state analyzed
- No conflicts found
- Dependencies available
- Patterns established

**Next Step**: User approval to begin implementation.
