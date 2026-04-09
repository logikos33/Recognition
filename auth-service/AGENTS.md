<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-09 -->

# auth-service

Isolated JWT authentication microservice. Manages user registration, login, token refresh, and validation.

## Purpose

Single responsibility: user identity and access control. All other services delegate auth validation to this service via JWT token verification.

## Architecture

```
POST /api/auth/register     → create_user()  → users table
POST /api/auth/login        → verify_password() → generate JWT + refresh token
POST /api/auth/refresh      → validate_refresh_token() → new JWT
POST /api/auth/logout       → revoke_refresh_token() → Redis delete
POST /api/auth/validate     → decode_jwt() → {user_id, email, expires_at}
GET  /api/auth/me           → get_current_user() → {id, email, name, company}
GET  /health                → database ping + Redis ping
```

## Package Structure

```
authsvc/
├── __init__.py
├── main.py              # Entry point: create_app() + run server
├── app.py               # Flask app factory
├── config.py            # Environment config
├── routes.py            # All endpoints
├── db.py                # PostgreSQL connection pool (psycopg2)
├── user_repo.py         # User repository (queries)
├── jwt_handler.py       # JWT encode/decode, validation
├── password.py          # bcrypt hash/verify
├── session_store.py     # Redis refresh token storage
```

## Key Dependencies

- `flask>=3.0.0` — Web framework
- `redis>=5.0.0` — Refresh token store (TTL-based)
- `psycopg2-binary>=2.9.0` — PostgreSQL direct access
- `PyJWT>=2.8.0` — Token encoding/decoding
- `bcrypt>=4.1.0` — Password hashing

## Endpoints

### Registration
```bash
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "John Doe",
  "company": "ACME Corp"
}

Response (201):
{
  "status": "success",
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

### Login
```bash
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

Response (200):
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGc...",
    "refresh_token": "ref_...",
    "token_type": "Bearer",
    "expires_in": 3600
  }
}
```

### Token Refresh
```bash
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "ref_..."
}

Response (200):
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGc...",
    "expires_in": 3600
  }
}
```

### Validate Token
```bash
POST /api/auth/validate
Authorization: Bearer eyJhbGc...

Response (200):
{
  "status": "success",
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "expires_at": "2026-04-09T18:00:00Z"
  }
}
```

### Get Current User
```bash
GET /api/auth/me
Authorization: Bearer eyJhbGc...

Response (200):
{
  "status": "success",
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "company": "ACME Corp"
  }
}
```

### Logout
```bash
POST /api/auth/logout
Authorization: Bearer eyJhbGc...

Response (200):
{
  "status": "success",
  "message": "Logged out successfully"
}
```

## Database Access

Reads/writes `users` table directly via psycopg2:

```python
# users table schema
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(255),
  company VARCHAR(255),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE
);
```

No ORM — raw SQL with parameterized queries via `psycopg2.extras.RealDictCursor`.

## Redis Usage

Stores refresh tokens with TTL (7 days by default):

```
Key: refresh_token:{token_hash}
Value: {user_id}
TTL: 604800 (seconds)
```

On logout, refresh token is deleted from Redis.

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# JWT
JWT_SECRET_KEY=min-32-chars-random-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRES=3600           # seconds
JWT_REFRESH_TOKEN_EXPIRES=604800        # seconds (7 days)

# Redis
REDIS_URL=redis://host:6379/0

# Flask
FLASK_ENV=production
SECRET_KEY=min-32-chars-random-secret
PORT=8005

# Optional
BCRYPT_LOG_ROUNDS=12
```

## Health Check

```bash
GET /health

Response (200):
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}

Response (503):
{
  "status": "unhealthy",
  "database": "error: connection timeout",
  "redis": "connected"
}
```

## Error Responses

```json
{
  "status": "error",
  "message": "Invalid credentials",
  "code": "AUTH_001"
}
```

Common codes:
- `AUTH_001` — Invalid email/password
- `AUTH_002` — User not found
- `AUTH_003` — Token expired
- `AUTH_004` — Token invalid
- `AUTH_005` — Email already registered

## Testing

```bash
# Health
curl http://localhost:8005/health

# Register
curl -X POST http://localhost:8005/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@local.dev","password":"Pass123!","name":"Test"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:8005/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@local.dev","password":"Pass123!"}' | jq -r '.data.access_token')

# Validate
curl http://localhost:8005/api/auth/validate \
  -H "Authorization: Bearer $TOKEN"
```

## Service Dependencies

- **PostgreSQL** — User storage (railway plugin)
- **Redis** — Session/token store (railway plugin)

No dependencies on other microservices.

## Deployment

Railway automatically detects and runs:
```
CMD ["python", "-m", "authsvc.main"]
```

Set `PORT` in Railway Variables (default: 8005).
