# auth-service/authsvc — AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Mission

Auth Service provides JWT-based authentication and user management for the EPI Monitor system.

**Responsibilities**:
- User registration and login
- JWT token generation and validation
- Refresh token management via Redis
- User profile retrieval
- Session lifecycle management

## Architecture

### Startup Sequence (main.py)

```
_startup()
  ├─ check PostgreSQL connectivity via _get_pool()
  ├─ log "auth_db_ok"
  ├─ register signal handlers
  └─ Flask.run() [blocks on main thread]

on SIGTERM/SIGINT:
  └─ sys.exit(0)
```

**Simple bootstrap**: Verifies database once, then serves requests.

## Modules

### main.py — Entrypoint

Minimal startup: check DB, register signals, run Flask.

### app.py — Flask Factory

Flask app with Blueprint registration. Blueprint prefix: `/api/auth`

**Routes** (via routes.py):
- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/validate`
- `GET /api/auth/me`

### routes.py — Endpoint Handlers

**POST /api/auth/login**
```json
Request: {"email": "user@example.com", "password": "secret"}
Response (200): {
  "success": true,
  "data": {
    "token": "<access_jwt>",
    "refresh_token": "<refresh_jwt>",
    "user": {"id": "uuid", "email": "user@example.com", "name": "John", "role": "operator"}
  }
}
Error (401): {"error": "Credenciais inválidas"}
```

**POST /api/auth/register**
```json
Request: {
  "email": "user@example.com",
  "password": "secret",
  "name": "John Doe"  (or "full_name")
}
Response (201): {
  "success": true,
  "data": {"user": {...}}
}
Error (400): {"error": "Email já cadastrado"} or missing fields
```

**POST /api/auth/refresh**
```json
Request: {"refresh_token": "<refresh_jwt>"}
Response (200): {
  "success": true,
  "data": {
    "token": "<new_access_jwt>",
    "refresh_token": "<new_refresh_jwt>"
  }
}
Error (401): {"error": "Token inválido"} or revoked
```

**POST /api/auth/logout**
```
Request: Authorization: Bearer <token>
Response (200): {"success": true}
```

**POST /api/auth/validate**
```json
Request: {"token": "<jwt>"}
Response (200): {"valid": true, "payload": {...}}
Response (401): {"valid": false}
```

**GET /api/auth/me**
```
Request: Authorization: Bearer <token>
Response (200): {"success": true, "data": {"user": {...}}}
Response (401): {"error": "Não autenticado"}
```

### db.py — Database Connection

**Pattern**: ThreadedConnectionPool + context manager

```python
class _DBPool:
    _pool = None
    
    @classmethod
    def get(cls):
        if cls._pool is None:
            cls._pool = ThreadedConnectionPool(1, 5, dsn)
        return cls._pool

@contextmanager
def get_conn():
    conn = _DBPool.get().getconn()
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        _DBPool.get().putconn(conn)
```

**URL Normalization**: Handles `postgres://` → `postgresql://` conversion.

### user_repo.py — User CRUD

**Methods**:
- `get_by_email(email: str)` → dict (with `id`, `email`, `password_hash`, `name`, `role`, `is_active`)
- `get_by_id(user_id: str)` → dict (same fields)
- `create_user(email, password_hash, name)` → dict

**Key Fields**:
- `id` (UUID primary key)
- `email` (unique, lowercase)
- `password_hash` (bcrypt)
- `name` (NOT `full_name`; note column difference)
- `role` (default: `"operator"`)
- `is_active` (boolean, default True)

**Query Pattern**: Direct SQL with `RealDictCursor` for named tuple access.

```python
with get_conn() as conn:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email.lower(),))
        return cur.fetchone()
```

### password.py — Hashing

**Functions**:
- `hash_password(plain: str) -> str` — bcrypt hash
- `check_password(plain: str, hashed: str) -> bool` — bcrypt verify

### jwt_handler.py — Token Management

**Functions**:
- `create_access_token(user_id, email, role) -> str` — JWT with type="access"
- `create_refresh_token(user_id) -> str` — JWT with type="refresh"
- `verify_token(token: str) -> dict` — Decodes and validates JWT
- `decode_unsafe(token: str) -> dict` — Decodes without validation (for type checking)

**Token Structure**:
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "role": "operator",
  "type": "access",
  "exp": 1680000000,
  "iat": 1679900000
}
```

**Token Lifetimes**:
- Access: 15 minutes (short-lived)
- Refresh: 7 days (long-lived)

### session_store.py — Refresh Token Storage

**Methods**:
- `store_refresh(user_id, token)` — Stores in Redis with TTL 7 days
- `get_refresh(user_id) -> str` — Retrieves from Redis (nil if expired/revoked)
- `revoke_refresh(user_id)` — Deletes key from Redis

**Key**: `refresh:{user_id}`
**Value**: Refresh token string
**TTL**: 7 days

## Configuration (config.py)

```python
PORT = 5001
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://...")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "secret-min-32-chars")
JWT_ALGORITHM = "HS256"
```

## PostgreSQL Schema (users table)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'operator',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Note**: Column is `name`, not `full_name`. Both names are accepted in register route for backwards compatibility.

## Redis Keys

| Key | Type | TTL | Set By | Read By |
|-----|------|-----|--------|---------|
| `refresh:{user_id}` | string | 7 days | session_store.store_refresh() | session_store.get_refresh() |

## Authentication Flow

### Login
```
POST /api/auth/login
  ├─ hash email (lowercase)
  ├─ query users table by email
  ├─ verify password with bcrypt
  ├─ create access + refresh tokens
  ├─ store refresh in Redis
  └─ return tokens + user
```

### Token Refresh
```
POST /api/auth/refresh
  ├─ decode refresh token (unsafe)
  ├─ check type=="refresh"
  ├─ verify token is in Redis (not revoked)
  ├─ verify user exists and is active
  ├─ create new access + refresh tokens
  ├─ update Redis with new refresh token
  └─ return new tokens
```

### Logout
```
POST /api/auth/logout
  ├─ extract token from Authorization header
  ├─ decode token safely
  ├─ revoke refresh token in Redis
  └─ return success
```

### Protected Routes
```
GET /api/auth/me
  ├─ extract token from Authorization header
  ├─ decode token safely
  ├─ query user by ID
  └─ return user profile
```

## Error Handling

| Error | HTTP Status | Response |
|-------|-------------|----------|
| Missing email/password | 400 | `{"error": "... são obrigatórios"}` |
| Invalid credentials | 401 | `{"error": "Credenciais inválidas"}` |
| Email already exists | 400 | `{"error": "Email já cadastrado"}` |
| Invalid token | 401 | `{"error": "Token inválido"}` or `{"error": "Não autenticado"}` |
| Revoked refresh token | 401 | `{"error": "Token revogado"}` |
| User not found | 404 | `{"error": "Usuário não encontrado"}` |
| DB connection error | 500 | `{"error": "Erro ao criar usuário"}` |

## Security

- **Password hashing**: bcrypt with 12 rounds
- **Token signing**: HMAC-SHA256
- **Token validation**: Signature + expiration + type check
- **Token storage**: Refresh tokens in Redis (not returned to client on logout)
- **Email normalization**: Lowercase before lookup (case-insensitive)
- **Active flag**: User deactivation blocks login + refresh

## Logging

Key events:
- `auth_db_ok` / `auth_db_fail`
- `login_ok: email=...`
- `register_error: ...`

## Testing Notes

```bash
# 1. Register user
curl -X POST http://localhost:5001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"secret123","name":"John"}'

# 2. Login
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"secret123"}'

# 3. Use token
TOKEN="eyJhbGc..."
curl http://localhost:5001/api/auth/me \
  -H "Authorization: Bearer $TOKEN"

# 4. Refresh
curl -X POST http://localhost:5001/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"..."}'

# 5. Logout
curl -X POST http://localhost:5001/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

## Known Limitations

- No password reset endpoint
- No email verification
- No account locking on failed attempts
- No audit logging of logins
- Refresh tokens stored in Redis (lost on server restart)
