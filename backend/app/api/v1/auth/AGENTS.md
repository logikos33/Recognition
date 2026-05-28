<!-- Parent: ../AGENTS.md -->

# auth — JWT Authentication

User registration, login, and profile management.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register new user (email, password, name) |
| `/api/auth/login` | POST | Login, returns JWT token with tenant_id + role claims |
| `/api/auth/me` | GET | Get current user profile (requires JWT) |

**Key Notes:**
- No JWT required for register/login
- JWT required for `/me`
- Passwords hashed with bcrypt
- Default admin: `admin@epimonitor.com` / `EpiMonitor@2024!`
- Additional claims stored in token: `tenant_id`, `email`, `role`
