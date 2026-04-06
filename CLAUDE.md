# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EPI Monitor V2** — Sistema de Monitoramento CCTV com IA para Baias de Carregamento da Ambev.

Sistema de visão computacional que usa câmeras CCTV existentes para:
- Detectar automaticamente quando um caminhão entra na baia
- Capturar a placa do veículo via OCR
- Contar cada produto carregado em tempo real (YOLOv8)
- Encerrar a sessão quando o caminhão sai
- Enviar para validação do operador
- Gerar relatórios em Excel e KPIs em dashboard

### V2 vs V1 — Why Rewrite

A V1 chegou a ~90% mas acumulou débitos técnicos:
- `api_server.py` com 3900 linhas (impossível manter)
- Vazamentos de conexão com banco (`next(get_db())`)
- FFmpeg e YOLO no mesmo container da API
- Polls com `setInterval` fixo (flood de requests)
- Tudo em um único serviço Railway ($150/mês para 5 câmeras)

**V2**: Arquitetura de microserviços, ~$70/mês para 5 câmeras com performance superior.

---

## Tech Stack

### Backend
- Python 3.11 + Flask (framework web)
- Flask-JWT-Extended (auth)
- Flask-SocketIO + Eventlet (WebSocket real-time)
- psycopg2-binary (PostgreSQL)
- bcrypt (hash de senhas)
- cryptography/Fernet (criptografia de senhas de câmeras)
- redis (event bus)
- gunicorn + eventlet (produção)

### AI/ML (Worker)
- YOLOv8 via Ultralytics
- FFmpeg (RTSP → HLS)
- OpenCV + PyTorch

### Frontend
- React 18 + TypeScript + Vite
- React Router (SPA)
- Recharts (dashboard charts)

### Database
- PostgreSQL 15
- Migrations SQL numeradas (`001_`, `002_`)
- UUIDs como primary keys
- `user_id` em TODAS as tabelas desde o início

### Infra
- Railway (PaaS)
- Nixpacks (build com FFmpeg)
- GitHub branches: `develop` / `staging` / `main`

---

## Architecture — Microservices

```
┌─────────────────┐         ┌─────────────────┐
│  API Flask      │◄───────►│   PostgreSQL    │
│  (routes, auth, │         │   (dados)       │
│   dashboard)    │         └─────────────────┘
└────────┬────────┘                 ▲
         │                          │
         │ Redis                    │
         │ (event bus)              │
         ▼                          │
┌─────────────────┐         ┌─────────────────┐
│   Worker        │         │      Redis      │
│  (FFmpeg+YOLO)  │         │   (event bus)   │
│                 │         └─────────────────┘
└─────────────────┘
```

**Scale**: 1 Worker por 3-4 câmeras (~1.5GB RAM por instância)

---

## Development Commands

### Local Development
```bash
# Backend (API)
export FLASK_ENV=development
export SERVICE_TYPE=api
python3 -m api.app  # ou gunicorn api.app:app

# Worker
export SERVICE_TYPE=worker
export WORKER_ID=worker-1
python3 worker/worker_server.py

# Frontend
cd frontend && npm run dev

# Migrations manual
for f in migrations/*.sql; do
  psql $DATABASE_URL -f "$f"
done
```

### Testing & Validation
```bash
# Smoke test (obrigatório antes de merge para staging/main)
./scripts/smoke_test.sh http://localhost:5001

# Teste em staging
./scripts/smoke_test.sh $RAILWAY_URL
```

### Git Workflow
```
develop  → desenvolvimento ativo
staging  → Railway staging (pré-produção)
main     → produção (apenas via PR de staging)
```

**NEVER** push direto em `main`. Sempre PR de `staging` para `main`.

---

## ABSOLUTE RULES — NEVER VIOLATE

### Backend
- ❌ `next(get_db())` → ✅ **SEMPRE** `with get_db_connection() as conn:`
- ❌ Arquivos >200 linhas → ✅ Blueprints por domínio
- ❌ Secrets hardcoded → ✅ **SEMPRE** `os.environ.get()`
- ❌ PORT hardcoded → ✅ `int(os.environ.get('PORT', 5001))`
- ❌ `postgres://` direto → ✅ corrigir `postgresql://` no startup
- ❌ `DROP TABLE` / `RENAME` → ✅ **APENAS** `ADD COLUMN IF NOT EXISTS`
- ❌ Endpoint sem `try/except` → ✅ handler em todo endpoint

### Frontend
- ❌ `setInterval` fixo → ✅ **exponential backoff** em TODOS os polls (use `usePolling` hook)
- ❌ Token com chave diferente → ✅ `getToken()` centralizado
- ❌ `api.logout()` (pode não existir) → ✅ `handleLogout` inline
- ❌ Dados mockados → ✅ zero mock — tudo conectado ao backend
- ❌ `App.tsx` >100 linhas → ✅ máx 100 linhas, lógica em hooks
- ❌ Componente >200 linhas → ✅ dividir em componentes menores

### Database
- ❌ `DROP` em produção → ✅ **APENAS** `CREATE IF NOT EXISTS`
- ❌ Tabelas sem `user_id` → ✅ **TODAS** as tabelas têm `user_id` desde o início
- ❌ `SELECT *` sem filtro de user → ✅ operator vê apenas seus dados, admin vê tudo

### Railway
- ❌ Nome de módulo errado no gunicorn → ✅ verificar `api.app:app` antes
- ❌ Frontend servido pelo Vite em produção → ✅ `npm build` + Flask serve estático
- ❌ Tudo em um container → ✅ API (`SERVICE_TYPE=api`) e Worker (`SERVICE_TYPE=worker`) separados

---

## Project Structure

```
├── api/
│   ├── app.py                 # Flask app factory — entry point para gunicorn
│   ├── blueprints/
│   │   ├── auth/              # register, login, me
│   │   ├── cameras/           # CRUD + stream control
│   │   ├── training/          # upload, frames, anotação, YOLO
│   │   ├── rules/             # rules engine, templates
│   │   ├── dashboard/         # KPIs, Excel export
│   │   └── streams/           # status público (sem JWT)
│   └── utils/
│       ├── auth.py            # hash_password, check_password, get_current_user
│       ├── responses.py       # success(), error()
│       └── worker_proxy.py    # API→Worker via Redis
├── worker/
│   └── worker_server.py       # FFmpeg+YOLO isolado, Redis events
├── services/shared/
│   ├── database.py            # get_db_connection() context manager
│   └── events.py              # EventPublisher (Worker), EventConsumer (API)
├── frontend/
│   └── src/
│       ├── components/        # componentes reutilizáveis
│       ├── hooks/             # usePolling, useAuth, etc.
│       ├── pages/             # Login, Cameras, Training, Rules, Dashboard
│       ├── services/          # api.ts (centralizado)
│       └── types/             # TypeScript types
├── migrations/                # 001_users.sql, 002_cameras.sql, etc.
├── storage/                   # training_videos, frames, streams, models
├── scripts/
│   └── smoke_test.sh          # testes obrigatórios antes de merge
├── nixpacks.toml              # build config (inclui FFmpeg)
├── railway.toml               # deploy config
└── railway_start.py           # inicialização Railway robusta
```

---

## Security Requirements

1. **Senhas de câmeras**: Criptografia Fernet (AES-128) no banco. **NUNCA** retornar na API.
2. **Secrets**: 100% via variáveis de ambiente. `.env` no `.gitignore`.
3. **JWT**: Todos os endpoints exceto `/health` e `/api/streams/status`.
4. **Isolamento**: `user_id` em todas as queries. Operator vê só seus dados.
5. **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, etc.
6. **CORS**: Configurável via `CORS_ORIGINS` env var. **NUNCA** `*` em produção.

---

## Common Patterns

### Database Connection (OBRIGATÓRIO)
```python
from services.shared.database import get_db_connection

# ✅ CORRETO — sempre fecha a conexão
with get_db_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT ...", (param,))
    result = cur.fetchall()

# ❌ ERRADO — causa pool exhaustion (90% dos crashes V1)
conn = next(get_db())
```

### Frontend Polling (OBRIGATÓRIO)
```typescript
import { usePolling } from '@/hooks/usePolling'

usePolling(
  async () => { await fetchData() },
  5000,  // intervalo base
  { maxInterval: 60000 }  // backoff máximo
)
```

### API Response (OBRIGATÓRIO)
```python
from api.utils.responses import success, error

return success(data, status=201)
return error('Mensagem', status=400)
```

---

## Environment Variables

### API
- `SERVICE_TYPE=api` — define que este serviço é a API
- `JWT_SECRET_KEY` — segredo para tokens JWT
- `SECRET_KEY` — segredo Flask
- `CAMERA_SECRET_KEY` — chave Fernet para senhas de câmeras
- `CORS_ORIGINS` — origins permitidas (separadas por vírgula)
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `FLASK_ENV` — `development` ou `production`

### Worker
- `SERVICE_TYPE=worker` — define que este serviço é Worker
- `WORKER_ID` — identificador único (`worker-1`, `worker-2`, etc.)
- `YOLO_MODEL_PATH` — caminho para modelo YOLO
- `DATABASE_URL` — PostgreSQL (compartilhado)
- `REDIS_URL` — Redis (event bus)

### Admin (criado automaticamente no primeiro deploy)
- `ADMIN_EMAIL` — padrão: `admin@epimonitor.com`
- `ADMIN_PASSWORD` — padrão: `EpiMonitor@2024!`
- `ADMIN_NAME` — padrão: `Administrador`

---

## Railway Deployment

### API Service
```bash
railway up --service-type api
# Variáveis: SERVICE_TYPE=api
```

### Worker Service (adicionar quando necessário)
```bash
railway add --service worker
# Variáveis: SERVICE_TYPE=worker, WORKER_ID=worker-1
```

### Health Check
Railway usa `/health` para healthcheck. Retorna:
- `200` — database OK
- `503` — database com problema

---

## Database URL Fix (Railway)

Railway retorna `postgres://` mas `psycopg2` precisa `postgresql://`. Correção automática em `railway_start.py`:

```python
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)
```

---

## Default Admin Credentials

```
Email: admin@epimonitor.com
Senha: EpiMonitor@2024!
```

**IMPORTANTE**: Alterar em produção.

## 🎯 Identidade do Projeto

**EPI Monitor** é um sistema de monitoramento de EPIs (Equipamentos de Proteção
Individual) via câmeras CCTV com detecção por YOLOv8. Desenvolvido por Lucas
(Evoluke/Logikos) e Vitor Emanuel.

**Stack produção (Railway)**:
- `service api` → Flask + SocketIO + gunicorn/eventlet
- `service worker` → Celery (FFmpeg, inference, HLS, versioning)
- `service frontend` → React 18 + TypeScript + nginx
- `plugin PostgreSQL` → psycopg2 direto, sem ORM
- `plugin Redis` → Celery broker + SocketIO message_queue + pub/sub
- `external Cloudflare R2` → object storage S3-compatível (boto3)
- `external Vast.ai` → GPU para treino YOLOv8 (pay-as-you-go via SSH)

**Branch ativa**: V2-clean → Main (produção Railway)

---

## ⚡ Filosofia de Trabalho — Autonomia Total

Claude trabalha de forma **contínua, autônoma e sem pausas** neste projeto.

### Princípios de autonomia

**Nunca pare para perguntar sobre**:
- Qual design pattern usar → escolha o mais adequado para o contexto
- Qual nome de variável, função ou arquivo → use nomenclatura consistente com o código existente
- Se deve criar um teste → sempre crie, mínimo 80% de cobertura
- Qual versão de biblioteca usar → a mais recente estável compatível com o projeto
- Como organizar um módulo novo → siga a estrutura de diretórios existente

**Quando houver incerteza genuína**:
1. Escolha a opção mais conservadora e coerente com a arquitetura existente
2. Registre a decisão em `DECISIONS.md` com: data, contexto, opções consideradas, escolha feita
3. Continue trabalhando sem parar

**Quando encontrar um erro**:
1. Leia o erro completo
2. Identifique a causa raiz (não apenas o sintoma)
3. Corrija na camada correta (não corrija sintomas)
4. Rode os testes novamente
5. Continue — não reporte erros intermediários, apenas resultados finais

**Meta de cada sessão**: sair com código funcionando, testado e commitado.
Código pela metade ou testes falhando não é aceitável como estado final de sessão.

### O que registrar no DECISIONS.md

```markdown
## [DATA] — Título da decisão
**Contexto**: O que motivou a decisão
**Opções consideradas**: A, B, C
**Escolha**: B
**Razão**: Justificativa técnica
**Impacto**: Quais arquivos/módulos afetados
```

---

## 👥 Time de Especialistas — Auto-organização

Claude atua como um time colaborativo. Cada especialista age no seu domínio
e todos trabalham em conjunto sem conflitos ou sobreposição.

### Como o time se organiza

Antes de iniciar qualquer tarefa, identifique internamente quais especialistas
estão envolvidos e coordene suas perspectivas na implementação:

```
[ARCH] Arquiteto de Software
  Domínio: estrutura, padrões, separação de camadas, SOLID, coesão
  Age quando: qualquer decisão que afete mais de um módulo
  Valida: nenhuma camada superior conhece implementação da inferior

[BE] Engenheiro Backend Python
  Domínio: Flask, Celery, Redis, boto3, SocketIO, psycopg2
  Age quando: qualquer arquivo Python de backend
  Padrão: Application Factory, Repository, Service Layer

[DB] Engenheiro de Banco de Dados
  Domínio: schema, migrations, queries, indices, connection pool
  Age quando: qualquer SQL ou acesso ao banco
  Regra: zero SQL fora dos repositories

[ML] Engenheiro de ML
  Domínio: YOLOv8, inferência, pipeline de treino, Vast.ai
  Age quando: qualquer código envolvendo modelo ou visão computacional
  Padrão: inferência não bloqueia event loop

[FE] Engenheiro Frontend React
  Domínio: React 18, TypeScript, hooks, serviços, canvas, WebSocket
  Regra absoluta: AnnotationInterface.jsx NUNCA é tocado
  Padrão: Custom Hooks, Service Layer, TypeScript strict

[OPS] Engenheiro DevOps/Railway
  Domínio: Docker, railway.toml, nixpacks, env vars, health checks
  Age quando: qualquer configuração de deploy ou infra
  Responsável: 3 services + 2 plugins Railway funcionando

[SEC] Engenheiro de Segurança
  Domínio: JWT, CORS, validação de inputs, RTSPUrlValidator
  Age quando: qualquer dado que entra via HTTP ou RTSP
  Regra: CORS nunca é bare CORS(app)

[QA] Engenheiro de Qualidade
  Domínio: pytest, cobertura, testes de integração
  Age quando: após qualquer implementação nova
  Regra: número reportado de testes = número real do pytest
```

### Colaboração entre especialistas

Os especialistas não trabalham em silos — um arquivo pode envolver múltiplos:
- Uma route em `api/v1/videos/routes.py` → [BE] implementa, [SEC] valida inputs,
  [QA] escreve testes
- Uma migration em `migrations/005_cameras.sql` → [DB] escreve, [ARCH] valida
  que não quebra nenhum repository existente
- Uma Celery task de inferência → [ML] lógica YOLOv8, [BE] integração Celery,
  [OPS] garante que FFmpeg está no Dockerfile

---

## 🔒 Regras Absolutas — NUNCA Quebrar

Estas regras são invioláveis. Nenhuma justificativa técnica as sobrepõe.

### Componente congelado
```
AnnotationInterface.jsx está CONGELADO.
- Nunca modificar
- Nunca renomear
- Nunca mover de lugar
- Nunca refatorar
- Nunca adicionar ou remover props
Qualquer integração ADAPTA-SE ao seu contrato existente, não o contrário.
Antes de qualquer trabalho de anotação: ler o componente e documentar sua interface.
```

### Banco de dados
```
psycopg2 DIRETO. Sem SQLAlchemy. Sem qualquer ORM.
ThreadedConnectionPool obrigatório (sem criar conexões avulsas).
Todo SQL isolado nos repositories — zero SQL fora da camada infrastructure/database.
RealDictCursor como cursor_factory padrão.
```

### Segurança
```
CORS nunca é CORS(app) bare.
Sempre: CORS(app, origins=config.CORS_ORIGINS) com lista explícita.
CORS_ORIGINS nunca contém "*" em produção.
RTSPUrlValidator multi-layer antes de qualquer URL chegar ao FFmpeg (SEC-002).
JWT obrigatório em todas as rotas exceto /health e /login.
Zero SQL com f-string ou %-format com input do usuário.
```

### Bounding boxes (herança da Fase 1)
```
Todos os bounding boxes: pointerEvents: 'none'
Zero handlers onClick em qualquer bounding box
Eventos de mouse tratados matematicamente no handleMouseDown do container
handleFrameChange: async com await obrigatório
setSelectedFrame: apenas dentro de handleFrameChange e loadFrames
```

### Vite (path com espaço no projeto)
```
vite.config.ts obrigatoriamente:
  server: {
    usePolling: true,
    cacheDir: '/tmp/vite-cache-epi'
  }
```

### Qualidade
```
Nunca reportar número de testes diferente do output real do pytest.
Cobertura mínima: 80% por módulo.
TypeScript strict: true — zero any implícito.
Zero print() no backend — usar logging estruturado.
Zero console.log() no frontend em produção.
```

---

## 🏗️ Arquitetura (decisões imutáveis)

### Separação de camadas (SOLID — Dependency Inversion)

```
api/v1/          → Apresentação: routes, schemas de request/response
                   Conhece: domain/services (via injeção)
                   Nunca conhece: infrastructure diretamente

domain/          → Negócio puro: services, models (dataclasses)
                   Conhece: infrastructure abstractions (interfaces)
                   Nunca conhece: Flask, Celery, boto3, psycopg2

infrastructure/  → Implementações: database, storage, queue
                   Conhece: suas próprias libs (boto3, psycopg2, celery)
                   Expõe: interfaces abstratas para domain/

core/            → Utilitários transversais: exceptions, auth, responses
                   Usado por: todas as camadas
```

### Padrões de design obrigatórios

| Padrão | Onde | Por quê |
|---|---|---|
| Application Factory | `app/__init__.py` | Testabilidade, múltiplos ambientes |
| Repository | `infrastructure/database/repositories/` | Isola SQL, testável com mocks |
| Service Layer | `domain/services/` | Lógica de negócio sem dependência de infra |
| Strategy | `infrastructure/storage/base.py` | R2 hoje, S3 amanhã sem reescrita |
| Observer | Redis pub/sub → SocketIO | Desacopla worker de apresentação |
| Command | Celery tasks | Encapsula operações assíncronas |
| Dependency Injection | `__init__` dos services | Testabilidade, sem globais implícitos |

### Comunicação em tempo real (padrão fixo)

```
Worker Celery → redis.publish(f"det:{cam_id}", json)
                         ↓
Flask-SocketIO (message_queue=REDIS_URL) → socketio.emit(f"det_{cam_id}", data)
                         ↓
               Browser (socket.io-client)
```

Worker **nunca** emite WebSocket diretamente. Sempre via Redis pub/sub.

### Hierarquia de exceções customizadas

```python
EpiMonitorError          # base
├── StorageError         # R2, file ops
├── DatabaseError        # psycopg2 wrapping
├── ValidationError      # inputs inválidos
├── TrainingError        # Vast.ai, YOLOv8
├── InferenceError       # runtime de detecção
└── AuthenticationError  # JWT, permissões

# Exceções de infraestrutura são SEMPRE capturadas e re-raised
# como exceções de domínio — nunca vazar detalhes de infra ao cliente.
```

---

## 📁 Estrutura de Diretórios (referência rápida)

```
backend/
├── app/
│   ├── __init__.py          # create_app(config_name)
│   ├── extensions.py        # socketio, celery init
│   ├── config.py            # Config por ambiente
│   ├── constants.py         # Enums, R2Prefix, RedisChannels
│   ├── api/v1/              # Routes por domínio (Blueprint)
│   │   ├── auth/
│   │   ├── videos/
│   │   ├── frames/
│   │   ├── annotations/
│   │   ├── datasets/
│   │   ├── training/
│   │   ├── cameras/
│   │   └── health/
│   ├── core/
│   │   ├── exceptions.py    # Hierarquia de exceções
│   │   ├── responses.py     # success_response(), error_response()
│   │   ├── middleware.py    # Request logging, error handlers
│   │   ├── auth.py          # JWT decode/encode, @jwt_required
│   │   └── validators.py    # RTSPUrlValidator, VideoUploadValidator
│   ├── domain/
│   │   ├── models/          # Dataclasses por entidade
│   │   └── services/        # Use cases, lógica de negócio
│   └── infrastructure/
│       ├── database/
│       │   ├── connection.py        # ThreadedConnectionPool
│       │   ├── repositories/        # Um por entidade
│       │   └── migrations/          # SQL numerados + run_migrations.py
│       ├── storage/
│       │   ├── base.py              # StorageStrategy (ABC)
│       │   └── r2_storage.py        # R2Storage implementation
│       └── queue/
│           ├── celery_app.py        # Celery factory
│           └── tasks/
│               ├── extraction.py
│               ├── quality.py
│               ├── versioning.py
│               ├── training.py
│               └── inference.py
└── tests/
    ├── conftest.py
    ├── unit/
    └── integration/

frontend/
├── src/
│   ├── components/
│   │   ├── annotation/
│   │   │   └── AnnotationInterface.jsx  # ← CONGELADO
│   │   ├── monitoring/
│   │   ├── training/
│   │   ├── upload/
│   │   └── shared/
│   ├── hooks/              # useSocket, useCameraStream, useTraining...
│   ├── services/           # api.ts, videoService, cameraService...
│   ├── types/              # Interfaces TypeScript por domínio
│   ├── stores/             # Context API (apenas quando necessário)
│   └── pages/              # UploadPage, AnnotationPage, TrainingPage, MonitoringPage
├── nginx.conf
├── Dockerfile.frontend
└── nixpacks.toml
```

---

## 🛠️ Padrões Técnicos

### Python (backend)

```python
# Type hints obrigatórios em 100% das assinaturas públicas
def create_video(self, dataset_id: UUID, filename: str) -> Video: ...

# Docstrings formato Google em classes e funções públicas
def generate_upload_url(self, dataset_id: UUID, filename: str) -> tuple[str, UUID]:
    """Valida extensão e gera presigned URL para upload direto ao R2.

    Args:
        dataset_id: UUID do dataset de destino.
        filename: Nome original do arquivo enviado pelo usuário.

    Returns:
        Tupla (presigned_url, video_id).

    Raises:
        ValidationError: Se extensão não permitida ou filename inválido.
        StorageError: Se falha ao gerar presigned URL no R2.
    """

# Logging estruturado (nunca print)
import logging
logger = logging.getLogger(__name__)
logger.info("frame_extracted", extra={"frame_id": frame_id, "dataset_id": dataset_id})

# Constantes via enum ou constants.py (nunca magic strings)
from app.constants import VideoStatus, R2Prefix, EpiClass

# Context manager para conexões de banco (nunca esquecer de devolver)
with self._db.get_connection() as conn:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
```

### TypeScript (frontend)

```typescript
// strict: true em tsconfig.json — zero any implícito
// Interfaces explícitas para todos os dados da API
interface Frame {
  id: string
  datasetId: string
  r2Key: string
  status: FrameStatus
  blurScore: number
  brightnessScore: number
}

// Custom hooks para toda lógica com estado
function useAnnotationQueue(datasetId: string) {
  const [currentFrame, setCurrentFrame] = useState<Frame | null>(null)
  // ...
  return { currentFrame, loadNext, saveLabels, progress }
}

// Service layer para todas as chamadas HTTP
// Nunca fetch/axios direto em componentes
const frame = await frameService.getNext(datasetId)

// Error boundaries em cada seção crítica
<ErrorBoundary fallback={<ErrorFallback />}>
  <AnnotationInterface {...props} />
</ErrorBoundary>
```

### SQL (repositories)

```sql
-- Sempre usar parâmetros posicionais, nunca f-string
SELECT * FROM dataset_frames
WHERE dataset_id = %s AND status = %s
ORDER BY created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- UUID como PK em todas as tabelas
-- Timestamps sempre com timezone (TIMESTAMP WITH TIME ZONE)
-- Status como VARCHAR com check constraint ou ENUM PostgreSQL
```

### Celery Tasks

```python
@celery.task(
    bind=True,
    max_retries=3,
    queue="extraction",
    acks_late=True  # ack só após sucesso
)
def extract_frames(self, video_key: str, video_id: str, dataset_id: str) -> dict:
    try:
        # implementação
        return {"status": "success", "frames_count": N}
    except Exception as exc:
        logger.error("task_failed", task="extract_frames",
                     video_id=video_id, error=str(exc), exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
```

### Responses padronizadas (via core/responses.py)

```python
# Sucesso
{"status": "success", "data": {...}}

# Erro
{"status": "error", "message": "Descrição legível", "code": "ERROR_CODE"}

# Nunca expor: stack traces, SQL errors, paths internos, credenciais
```

---

## 🚀 Railway — Referência de Deploy

### Services e start commands

```bash
# service: api
gunicorn -w 2 -k eventlet --worker-connections 1000 \
  --timeout 120 --bind 0.0.0.0:$PORT \
  --access-logfile - --error-logfile - \
  "app:create_app()"

# service: worker
celery -A app.infrastructure.queue.celery_app:celery worker \
  --loglevel=info --concurrency=2 --max-tasks-per-child=100 \
  --queues=extraction,quality,versioning,inference,training

# service: frontend
# Detectado automaticamente via nixpacks.toml → npm ci + npm run build
```

### Variáveis de ambiente (obrigatórias)

```bash
# Injetadas automaticamente pelos plugins Railway:
DATABASE_URL        # PostgreSQL plugin
REDIS_URL           # Redis plugin

# Configurar no Railway dashboard (Variables compartilhadas):
FLASK_ENV=production
SECRET_KEY=<min-32-chars-random>
R2_ENDPOINT=https://{account_id}.r2.cloudflarestorage.com
R2_BUCKET=epi-monitor
R2_KEY=<cloudflare-access-key>
R2_SECRET=<cloudflare-secret-key>
CORS_ORIGINS=https://epi-frontend.railway.app

# Apenas no service frontend:
VITE_API_URL=https://epi-api.railway.app
VITE_WS_URL=wss://epi-api.railway.app
```

### Health check

```
Path: /api/v1/health
Timeout: 300s
Verifica: PostgreSQL (SELECT 1), Redis (PING), R2 (list objects)
Retorna 200 se tudo ok, 503 se qualquer check falhar
```

### Filas Celery por prioridade

```
extraction  → extract_frames, quality_filter (alta prioridade, curtas)
versioning  → build_dataset_version (média, pode ser longa)
training    → dispatch_training (baixa, muito longa)
inference   → inference_loop, start_hls_stream (crítica, contínua)
```

---

## 🔑 Prefixos R2 (usar sempre as constantes de R2Prefix)

```
raw-videos/{dataset_id}/{video_id}.mp4
frames/{dataset_id}/{frame_id}.jpg
frames/{dataset_id}/rejected/{frame_id}.jpg
labels/{dataset_id}/{frame_id}.txt
datasets/v{X}.{Y}.{Z}/train/images/
datasets/v{X}.{Y}.{Z}/train/labels/
datasets/v{X}.{Y}.{Z}/val/images/
datasets/v{X}.{Y}.{Z}/val/labels/
datasets/v{X}.{Y}.{Z}/test/images/
datasets/v{X}.{Y}.{Z}/test/labels/
datasets/v{X}.{Y}.{Z}/metadata.json
models/{run_id}/best.pt
models/{run_id}/metrics_partial.json
evidence/{camera_id}/{timestamp_iso}.jpg
```

---

## 📦 Classes EPI (enum EpiClass — use sempre)

```
helmet, no_helmet
vest, no_vest
gloves, no_gloves
safety_glasses, no_safety_glasses
```

Anotar **ausências** é tão importante quanto as presenças.

---

## 🔄 Branching Strategy

```
V2 (desenvolvimento)
 └── feat/nome-da-feature    (features novas)
 └── fix/nome-do-bug         (correções)
 └── savepoint/fase-N-nome   (checkpoints de fase)
     └── → merge V2-clean    (staging)
         └── → merge Main    (produção Railway)
```

Commits seguem Conventional Commits:
```
feat(scope): o que foi adicionado
fix(scope): bug corrigido
refactor(scope): sem mudança de comportamento
test(scope): testes adicionados/corrigidos
docs(scope): documentação
chore(scope): manutenção
```

Scopes válidos: `foundation, infrastructure, ingestion, annotation,
training, monitoring, frontend, security, deploy, database`

---

## 🤝 Como Lidar com Situações Específicas

### Ao iniciar uma nova sessão
1. Ler este CLAUDE.md
2. Verificar o `DECISIONS.md` para entender decisões anteriores
3. Rodar `git status` e `git log --oneline -10` para ter contexto
4. Se houver testes falhando: corrigir antes de qualquer coisa nova
5. Continuar de onde a sessão anterior parou

### Ao criar um novo módulo
1. Verificar se já existe algo similar (buscar antes de criar)
2. Seguir a estrutura de diretórios exatamente
3. Criar o arquivo de testes junto com o arquivo de implementação
4. Registrar a criação no DECISIONS.md se envolver decisão de design

### Ao modificar código existente
1. Ler o arquivo na íntegra antes de qualquer mudança
2. Entender todos os usos do que vai ser modificado
3. Não mudar comportamento sem intenção explícita
4. Atualizar testes correspondentes
5. Se a mudança afeta a interface pública de uma classe: verificar todos os callers

### Ao encontrar um TODO ou código incompleto
1. Completar se estiver no escopo da tarefa atual
2. Se não estiver no escopo: adicionar ao DECISIONS.md como pendência
3. Nunca deixar código comentado (`# TODO: ...`) sem data e contexto

### Ao encontrar um design pattern diferente do especificado
1. Se o código existente usa um padrão diferente: avaliar se vale migrar
2. Se a migração quebrar muita coisa: manter o padrão existente e documentar
3. Nunca misturar dois padrões diferentes no mesmo módulo

### Ao ver uma dependência desatualizada
1. Verificar changelog para breaking changes
2. Se segura: atualizar e rodar testes
3. Se incerta: manter versão atual e documentar no DECISIONS.md

---

## ✅ Definição de "Tarefa Concluída"

Uma tarefa só está concluída quando:
- [ ] Código implementado e funcionando
- [ ] Testes escritos e passando (pytest output real)
- [ ] Cobertura ≥ 80% no módulo modificado
- [ ] TypeScript compila sem erros (se frontend)
- [ ] Zero linting errors (ruff no backend, eslint no frontend)
- [ ] Logging estruturado nos pontos críticos
- [ ] Docstrings nas classes e funções públicas novas
- [ ] Nenhuma magic string (tudo em constants.py ou enums)
- [ ] DECISIONS.md atualizado se houve decisão de design
- [ ] Commit com mensagem no padrão Conventional Commits

**Código que funciona mas não tem testes não está concluído.**
**Código que tem testes mas não passa no linter não está concluído.**

---

## 🚫 O que NUNCA fazer (além das regras absolutas)

- Criar conexão psycopg2 fora do connection pool
- Colocar lógica de negócio em routes (apenas delegação para services)
- Colocar SQL em services ou domain models (apenas em repositories)
- Fazer request HTTP em domain services (apenas via interfaces injetadas)
- Usar `global` em Python no backend
- Fazer `import *` em qualquer lugar
- Commitar arquivos `.env` ou qualquer credencial real
- Logar dados sensíveis (passwords, tokens, connection strings)
- Usar `subprocess.shell=True` com qualquer input do usuário
- Servir arquivos estáticos sem validar o path (path traversal)
- Expor stack traces ou mensagens de erro internas ao cliente
- Fazer build do frontend sem `npm ci` (sempre lockfile)

---

*Este arquivo é a fonte de verdade para qualquer decisão de desenvolvimento.
Em caso de conflito entre este arquivo e qualquer outro documento, este prevalece.*
