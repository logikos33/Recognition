# AGENT.md — services/api

**Serviço:** API v3 — Flask REST + SocketIO
**Responsabilidade:** Controller central da plataforma Recognition
**Railway service:** `api-v3`
**URL produção:** `https://api-v3-production-2b22.up.railway.app`

---

## Propósito

Expõe a API REST versionada `/api/v1/*` e o canal WebSocket via Flask-SocketIO. Concentra autenticação JWT, roteamento multi-tenant, despacho de tarefas Celery e a ponte Redis→WebSocket (`socket_bridge`).

---

## Stack

| Componente | Versão / Detalhe |
|-----------|-----------------|
| Python | 3.11 |
| Framework | Flask + flask-jwt-extended + Flask-SocketIO |
| Driver DB | psycopg2-binary (RealDictCursor) |
| Task client | Celery (apenas .delay() / .apply_async()) |
| Autenticação | JWT HS256 (usuários) + RS256 (device tokens, Fase 4) |
| Servidor WSGI | gunicorn + eventlet (Railway) |
| Entry point | `railway_start.py` com `SERVICE_TYPE=api` |

---

## Entry Point e Startup

```
railway_start.py
  └── SERVICE_TYPE=api
        └── gunicorn "app:create_app()" --worker-class eventlet
              └── app/__init__.py → create_app()
                    ├── registra blueprints
                    ├── inicializa DatabasePool
                    ├── inicializa SocketIO
                    ├── inicia socket_bridge (thread Redis pub/sub)
                    └── roda migrations (infra/migrations/*.sql)
```

---

## Estrutura de Diretórios

```
services/api/
├── app/
│   ├── __init__.py              # create_app() — Application Factory
│   ├── config.py                # Config por ambiente (dev/test/prod)
│   ├── constants.py             # Enums: UserRole, R2Prefix, EpiClass
│   ├── extensions.py            # jwt = JWTManager(), socketio = SocketIO()
│   ├── api/
│   │   └── v1/                  # Blueprints por domínio
│   │       ├── auth/routes.py          # POST /api/auth/login|register
│   │       ├── cameras/routes.py       # CRUD /api/cameras + stream control
│   │       ├── alerts/routes.py        # GET /api/alerts (filtros, export CSV)
│   │       ├── rules/routes.py         # Alert rules engine
│   │       ├── modules/routes.py       # GET /api/modules/{code}/classes|stats
│   │       ├── reports/routes.py       # GET /api/reports/home
│   │       ├── frames/routes.py        # POST /api/frames/{id}/pre-annotate
│   │       ├── dashboard/routes.py     # KPIs, Excel export
│   │       ├── training/routes.py      # Jobs, modelos, datasets
│   │       ├── edge/routes.py          # /api/v1/edge/* (Fase 2)
│   │       └── health/routes.py        # GET /health
│   ├── core/
│   │   ├── auth.py              # JWT helpers, get_current_user_id(), get_tenant_schema()
│   │   ├── responses.py         # success(data) / error(msg, status)
│   │   ├── exceptions.py        # EpiMonitorError hierarchy
│   │   ├── socket_bridge.py     # Thread que assina det:* no Redis e faz SocketIO broadcast
│   │   └── validators.py        # RTSPUrlValidator
│   ├── domain/
│   │   ├── models/              # Dataclasses por entidade (Camera, Alert, Rule, ...)
│   │   └── services/            # camera_service, alert_service, module_service, report_service, ...
│   └── infrastructure/
│       ├── database/
│       │   ├── connection.py    # DatabasePool (ThreadedConnectionPool singleton)
│       │   ├── migrations.py    # run_migrations() chamado no startup
│       │   └── repositories/    # BaseRepository + um por entidade
│       ├── hub/                 # Celery task dispatch helpers
│       ├── queue/               # Celery app configuration
│       └── storage/             # R2Storage (boto3, Cloudflare R2)
├── migrations/                  # Migrations locais do serviço (deprecated — usar infra/migrations/)
├── tests/
├── Dockerfile
├── pyproject.toml
├── railway.toml
├── AGENT.md                     # Este arquivo
└── SDD.md
```

---

## Padrão de Autenticação

```python
# Toda rota protegida usa o decorator do core:
from app.core.auth import jwt_required_custom, get_current_user_id, get_tenant_schema

@bp.route("/cameras", methods=["GET"])
@jwt_required_custom
def list_cameras(**kwargs):
    user_id = get_current_user_id()
    tenant_schema = get_tenant_schema()   # extrai do JWT claim
    repo = _get_repo(tenant_schema)
    ...
```

**Fluxo JWT:**
1. `POST /api/auth/login` → gera JWT HS256 com `user_id`, `tenant_id`, `tenant_schema`, `role`
2. Frontend inclui em todas as requests: `Authorization: Bearer <token>`
3. `jwt_required_custom` chama `verify_jwt_in_request()` e injeta `user_id` no kwargs
4. `get_tenant_schema()` lê `tenant_schema` do JWT identity

**Device tokens (Fase 4):**
- JWT RS256 com escopos limitados (`heartbeat:write`, `detection:write`, `config:read`)
- Chave privada armazenada apenas no cloud; edge recebe apenas o token assinado
- Ver ADR-0008

---

## Padrão de Database

```python
# 1. Obter instância do pool (singleton)
from app.infrastructure.database.connection import DatabasePool

def _get_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    return CameraRepository(pool)

# 2. Repository usa BaseRepository
class CameraRepository(BaseRepository):
    def list_by_tenant(self, tenant_schema: str) -> list[dict]:
        query = """
            SET search_path TO {schema}, public;
            SELECT * FROM cameras WHERE is_active = TRUE
        """.format(schema=tenant_schema)
        return self._execute(query)

# 3. BaseRepository expõe:
# _execute(query, params=None)          → list[dict]
# _execute_one(query, params=None)      → Optional[dict]
# _execute_mutation(query, params=None) → Optional[dict]  (INSERT/UPDATE com RETURNING)
```

**Regras absolutas:**
- Sem ORM, sem SQLAlchemy
- psycopg2 + RealDictCursor em todas as queries
- SQL explícito nos repositories — nunca em routes ou services
- Todo INSERT/UPDATE/DELETE usa parâmetros nomeados (`%(key)s`), nunca f-string com input do usuário
- `SET search_path TO {tenant_schema}, public` antes de toda query tenant-scoped

---

## Padrão de Response

```python
from app.core.responses import success, error

# Sucesso
return success({"cameras": items})                    # 200
return success({"camera": cam}, status=201)           # 201

# Erro
return error("Câmera não encontrada", 404)            # 404
return error("Dados inválidos", 400, "INVALID_IP")    # 400 com error_code
```

Envelope de resposta:
```json
{"success": true, "message": "OK", "data": {...}}
{"success": false, "error": "Câmera não encontrada"}
```

---

## Multi-tenant: Ciclo de Vida de Request

```
Request chega → flask_jwt_extended verifica token
                         ↓
              get_tenant_schema() lê claim do JWT
                         ↓
              _get_repo() cria repository com pool
                         ↓
              repository executa SET search_path TO {schema}, public
                         ↓
              query roda no schema do tenant
                         ↓
              success(data) retorna envelope padronizado
```

---

## Socket Bridge (Redis → WebSocket)

`app/core/socket_bridge.py` roda em thread background após o app iniciar:

```
Redis psubscribe("det:*")
  → a cada mensagem publicada pelo inference service
  → decodifica JSON (camera_id, detections, timestamp)
  → determina tenant_id pelo camera_id (lookup no pool)
  → socketio.emit("detection", payload, room=f"tenant:{tenant_id}")
  → frontend recebe via useMonitoringSocket hook
```

---

## Celery Client Dispatch

A API não processa tarefas pesadas — apenas despacha:

```python
from app.infrastructure.hub.task_dispatcher import dispatch_inference, dispatch_training

# Exemplos de dispatch
dispatch_inference(camera_id=str, frame_b64=str)
dispatch_training(job_id=str, dataset_path=str)
```

Filas disponíveis no worker: `inference`, `training`, `quality`, `versioning`.

---

## Variáveis de Ambiente Obrigatórias

| Variável | Descrição |
|---------|-----------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET_KEY` | Chave HS256 (mín. 32 chars) |
| `SERVICE_TYPE` | Deve ser `api` |
| `CORS_ORIGINS` | Whitelist CSV de origens permitidas |

---

## Comandos de Desenvolvimento

```bash
# Rodar localmente
cd services/api
export SERVICE_TYPE=api DATABASE_URL=... REDIS_URL=... JWT_SECRET_KEY=...
python3 -c "from app import create_app; app = create_app(); app.run(port=5001, debug=True)"

# Lint
python -m ruff check .
python -m mypy app/ --ignore-missing-imports

# Testes
python -m pytest tests/ -v --tb=short
```

---

## Restrições

- `CORS(app, origins=config.CORS_ORIGINS)` — nunca `CORS(app)` bare
- `RTSPUrlValidator` antes de qualquer URL chegar ao FFmpeg
- Zero SQL com f-string com input do usuário
- Zero `print()` — usar `logging.getLogger(__name__)`
- Toda nova tabela deve ter `tenant_id UUID REFERENCES tenants(id)` (exceto tabelas globais)
