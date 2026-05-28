# SDD — Software Design Document
# services/api — Flask API

**Versão:** 1.0
**Data:** 2026-05-28
**Status:** Ativo
**Serviço Railway:** `api-v3`

---

## Visão Geral

O `services/api` é o controller central da plataforma Recognition. Expõe uma API REST versionada `/api/v1/*` e um canal WebSocket via Flask-SocketIO para eventos em tempo real. Centraliza autenticação JWT, roteamento multi-tenant com schema PostgreSQL por tenant, despacho de tarefas para o Celery worker e a ponte Redis→WebSocket para broadcast de detecções ao frontend.

**Responsabilidades:**
- Autenticação e autorização de usuários (JWT HS256)
- Autenticação de dispositivos edge (JWT RS256, Fase 4)
- CRUD de câmeras, alertas, regras, módulos, relatórios, treinamento
- Endpoints de sync edge `/api/v1/edge/*` (Fase 2)
- Despacho de tarefas assíncronas (Celery client)
- Broadcast de detecções em tempo real (Socket Bridge)
- Execução de migrations no startup

---

## Componentes

### 1. Application Factory (`app/__init__.py`)

```
create_app(config_name=None)
  ├── Carrega Config (dev / test / prod)
  ├── Inicializa extensões: jwt, socketio, CORS
  ├── Registra blueprints de v1: auth, cameras, alerts, rules, modules,
  │   reports, frames, dashboard, training, edge, health
  ├── Inicializa DatabasePool (singleton)
  ├── Inicia socket_bridge em thread daemon
  └── Executa run_migrations() (apenas SERVICE_TYPE=api)
```

### 2. Blueprints (`app/api/v1/`)

Cada domínio tem seu próprio blueprint com prefixo `/api/v1/{domínio}`:

| Blueprint | Prefixo | Responsabilidade |
|-----------|---------|-----------------|
| `auth` | `/api/auth` | Login, register, refresh |
| `cameras` | `/api/cameras` | CRUD câmeras + stream control |
| `alerts` | `/api/alerts` | Listagem, filtros, export CSV |
| `rules` | `/api/rules` | Motor de regras de alerta |
| `modules` | `/api/modules` | Classes e stats por módulo |
| `reports` | `/api/reports` | KPIs, home report |
| `frames` | `/api/frames` | Pre-anotação de frames |
| `dashboard` | `/api/dashboard` | KPIs agregados, Excel export |
| `training` | `/api/training` | Jobs, modelos, datasets |
| `edge` | `/api/v1/edge` | Sync edge↔cloud (Fase 2) |
| `health` | `/health` | Healthcheck |

### 3. DatabasePool (`app/infrastructure/database/connection.py`)

Singleton que gerencia um `ThreadedConnectionPool` psycopg2:

```python
DatabasePool.get_instance()      # retorna o singleton
pool.getconn()                   # obtém conexão do pool
pool.putconn(conn)               # devolve ao pool
```

- Pool size: 5 min, 20 max (configurável por env)
- `RealDictCursor` como cursor factory padrão
- Reconexão automática em `OperationalError`

### 4. BaseRepository (`app/infrastructure/database/repositories/`)

Classe base que todos os repositories herdam:

```python
class BaseRepository:
    def __init__(self, pool: DatabasePool): ...
    def _execute(self, query, params=None) -> list[dict]: ...
    def _execute_one(self, query, params=None) -> Optional[dict]: ...
    def _execute_mutation(self, query, params=None) -> Optional[dict]: ...  # RETURNING
    def _set_search_path(self, conn, tenant_schema: str) -> None: ...
```

Repositories concretos:
- `CameraRepository` — câmeras, stream status
- `AlertRepository` — alertas, histórico, export
- `RuleRepository` — regras de alerta
- `UserRepository` — usuários, tenant lookup
- `ModuleRepository` — módulos, classes YOLO
- `TrainingRepository` — jobs, modelos, datasets
- `FrameRepository` — frames de treinamento, anotações
- `EdgeRepository` — device_tokens, heartbeats (Fase 4)

### 5. Socket Bridge (`app/core/socket_bridge.py`)

Thread daemon que conecta Redis pub/sub ao SocketIO:

```python
# Inicia no create_app()
def start_socket_bridge(socketio, pool):
    r = make_redis(for_subscribe=True)
    pubsub = r.pubsub()
    pubsub.psubscribe("det:*")       # assina todos os canais det:{camera_id}
    for message in pubsub.listen():
        payload = json.loads(message["data"])
        camera_id = payload["camera_id"]
        tenant_id = _get_tenant_for_camera(camera_id, pool)  # lookup no pool
        socketio.emit(
            "detection",
            payload,
            room=f"tenant:{tenant_id}",
            namespace="/"
        )
```

Frontend entra na room do seu tenant após conectar via `socket.emit("join", {"tenant_id": ...})`.

### 6. Celery Client Dispatch (`app/infrastructure/hub/`)

A API não processa tarefas pesadas. Apenas enfileira via `.delay()`:

```python
# task_dispatcher.py
from app.infrastructure.queue.celery_app import celery_app

def dispatch_inference(camera_id: str, frame_b64: str) -> None:
    celery_app.send_task("worker.inference", args=[camera_id, frame_b64], queue="inference")

def dispatch_training(job_id: str, dataset_path: str) -> None:
    celery_app.send_task("worker.training", args=[job_id, dataset_path], queue="training")
```

Filas disponíveis no worker: `inference`, `training`, `quality`, `versioning`.

---

## Interfaces

### REST API

**Autenticação:**
```
POST /api/auth/register   {email, password, full_name, tenant_schema?}
POST /api/auth/login      {email, password} → {token, user}
GET  /api/auth/me         → {user}
```

**Câmeras:**
```
GET    /api/cameras                   → {cameras: [...]}
POST   /api/cameras                   {name, ip, port, username, password, manufacturer, module_code}
GET    /api/cameras/{id}              → {camera}
PUT    /api/cameras/{id}              {campos a atualizar}
DELETE /api/cameras/{id}
POST   /api/cameras/{id}/stream/start
POST   /api/cameras/{id}/stream/stop
```

**Alertas:**
```
GET /api/alerts?camera_id=&module_code=&start=&end=&class_name=&page=
GET /api/alerts/export?format=csv
```

**Edge (Fase 2):**
```
POST /api/v1/edge/enroll              {device_id, one_time_token, site_id}
POST /api/v1/edge/heartbeat           {device_id, metrics}
POST /api/v1/edge/detections          {device_id, detections: [...]}
GET  /api/v1/edge/config/poll         ?device_id=&current_model_sha256=
POST /api/v1/edge/streams/report      {device_id, streams: [...]}
```

**Health:**
```
GET /health → {"status": "ok", "db": "ok", "redis": "ok", "version": "..."}
```

### WebSocket Events

| Evento | Direção | Payload |
|--------|---------|---------|
| `join` | client→server | `{tenant_id}` |
| `detection` | server→client | `{camera_id, detections[], has_violation, timestamp}` |
| `alert` | server→client | `{alert_id, camera_id, class_name, confidence, module_code}` |
| `stream_status` | server→client | `{camera_id, status}` |

---

## Fluxo de Dados

### Ciclo de vida de request multi-tenant

```
1. Request HTTP chega com Authorization: Bearer <token>
2. @jwt_required_custom verifica e decodifica JWT
3. get_current_user_id() → UUID do usuário
4. get_tenant_schema() → "rvb" (lido do JWT claim)
5. _get_repo() → Repository instanciado com DatabasePool
6. Repository._set_search_path(conn, "rvb")
   → executa: SET search_path TO rvb, public
7. Query SQL roda no schema "rvb"
8. success(data) retorna envelope padronizado
```

### Fluxo de alert (violação detectada)

```
1. Inference service publica det:{camera_id} no Redis
   {camera_id, detections: [{class: "no_helmet", confidence: 0.87, ...}], has_violation: true}
2. socket_bridge recebe via psubscribe("det:*")
3. Lookup: camera_id → tenant_id (cache em memória, TTL 5min)
4. socketio.emit("detection", payload, room="tenant:{tenant_id}")
5. Frontend recebe, renderiza overlay
6. Se has_violation=true:
   a. socket_bridge chama alert_service.create_alert(...)
   b. alert_service verifica regras ativas do tenant
   c. Se regra ativa: insere em alerts (PostgreSQL, schema do tenant)
   d. socketio.emit("alert", alert_payload, room="tenant:{tenant_id}")
```

---

## Dependências

| Dependência | Uso |
|------------|-----|
| `Flask` | Framework web |
| `flask-jwt-extended` | JWT HS256 + RS256 |
| `Flask-SocketIO` | WebSocket / long-polling |
| `psycopg2-binary` | Driver PostgreSQL |
| `celery[redis]` | Client para despacho de tarefas |
| `bcrypt` | Hash de senhas |
| `boto3` | Cloudflare R2 (storage de frames) |
| `gunicorn[eventlet]` | WSGI server em produção |
| `redis` | pub/sub + broker Celery |

**Variáveis de ambiente obrigatórias:**
- `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `SERVICE_TYPE=api`, `CORS_ORIGINS`

---

## Decisões Relevantes

| ADR | Impacto no serviço |
|-----|--------------------|
| ADR-0005 | Monorepo: serviço em `services/api/`, não mais `backend/` |
| ADR-0011 | Schema-per-tenant: `SET search_path` obrigatório em toda query tenant-scoped |
| ADR-0013 | Raw SQL + psycopg2: sem ORM, sem SQLAlchemy em nenhuma query |
| ADR-0014 | Railway Nixpacks: `railway_start.py` com `SERVICE_TYPE=api` |
| ADR-0008 | Device tokens RS256: blueprint `/api/v1/edge/*` usa verificação separada de JWT |
| ADR-0003 | Redis pub/sub: `socket_bridge` assina `det:*`; inference publica `det:{camera_id}` |

---

## Segurança

- `CORS(app, origins=config.CORS_ORIGINS)` — lista explícita, nunca wildcard
- `RTSPUrlValidator` valida toda URL antes de chegar ao FFmpeg
- Zero SQL interpolado com input do usuário — sempre `%(key)s` params
- Rate limiting via `flask-limiter` (configurar em Fase S1)
- Headers de segurança via `flask-talisman` (configurar em Fase S1)
- Audit log em `audit_log` table para: login, criação/edição/exclusão de cameras/rules/users

---

## Migrations

Executadas automaticamente no startup de `SERVICE_TYPE=api` via `run_migrations()`.

Localização: `infra/migrations/NNN_nome.sql`

Regras:
- Somente `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`
- Nunca `DROP`, `ALTER COLUMN TYPE`, `DELETE FROM`, `TRUNCATE`
- Toda nova tabela com `tenant_id UUID REFERENCES tenants(id)` (exceto globais)
- Migrations idempotentes: rodar 2x sem erro

Migration mais recente: verificar `ls infra/migrations/*.sql | sort | tail -1`
