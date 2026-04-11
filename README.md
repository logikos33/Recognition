# EPI Monitor V2

Sistema de monitoramento de EPIs via câmeras CCTV com detecção por YOLOv8.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| API | Flask + Flask-SocketIO + gunicorn/eventlet |
| Worker | Celery + Redis pub/sub |
| Frontend | React 18 + TypeScript + Vite |
| Database | PostgreSQL (psycopg2, sem ORM) |
| Storage | Cloudflare R2 (boto3) |
| Deploy | Railway (Nixpacks) |

## Desenvolvimento Local

### 1. Variáveis de Ambiente

```bash
cp backend/.env.example backend/.env
# Preencher DATABASE_URL e REDIS_URL (pode usar Railway CLI: railway run)
```

### 2. Backend (API)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export FLASK_ENV=development
python -m app  # ou: gunicorn "app:create_app()"
# API em http://localhost:5001
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# UI em http://localhost:3000
```

### 4. Worker (Celery)

```bash
cd backend
celery -A app.infrastructure.queue.celery_app:celery worker \
  --loglevel=info --queues=extraction,quality,inference
```

---

## RTSP Simulator (Desenvolvimento sem Câmera Real)

O simulador cria um stream RTSP local usando **MediaMTX** + **FFmpeg**.
Não requer câmera física. Funciona em macOS e Linux.

### Pré-requisitos

- FFmpeg instalado (`brew install ffmpeg` no macOS)
- Python 3.11+
- Acesso à internet (apenas no primeiro uso para baixar MediaMTX)

### Uso

```bash
cd backend/scripts

# Iniciar servidor RTSP + stream de vídeo sintético
python rtsp_simulator.py start

# Verificar status
python rtsp_simulator.py status

# Imprimir URL do stream
python rtsp_simulator.py url

# Parar tudo
python rtsp_simulator.py stop
```

### Stream URL

```
rtsp://localhost:8554/camera1
```

### Testar o Stream

```bash
# Via FFplay (incluído no FFmpeg)
ffplay rtsp://localhost:8554/camera1

# Via curl (listar metadados)
ffprobe rtsp://localhost:8554/camera1 -v quiet -print_format json -show_streams
```

### Adicionar câmera simulada à API

```bash
TOKEN=$(curl -s -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@epimonitor.com","password":"EpiMonitor@2024!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")

curl -X POST http://localhost:5001/api/cameras \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Câmera Simulada",
    "manufacturer": "generic",
    "host": "localhost",
    "port": 8554,
    "username": "",
    "rtsp_url_override": "rtsp://localhost:8554/camera1"
  }'
```

### O que o simulador faz

1. Baixa o binário **MediaMTX** (RTSP server leve, ~10MB) no primeiro uso
2. Gera um vídeo de teste sintético de 60s com FFmpeg `testsrc2`
3. Inicia o MediaMTX na porta 8554
4. Inicia FFmpeg em loop infinito publicando o vídeo no MediaMTX
5. PIDs salvos em `backend/scripts/bin/` para controle de ciclo de vida

---

## Deploy Railway

```bash
# Push e Railway faz o build automaticamente
git add . && git commit -m "feat: description" && git push origin staging

# Monitorar logs
railway logs --service API-V3
railway logs --service Worker

# Status dos services
railway service status
```

### Health Checks

```bash
# API
curl https://api-v3-production-2b22.up.railway.app/health

# Storage R2
curl https://api-v3-production-2b22.up.railway.app/api/v1/storage/health
```

---

## Endpoints Principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/auth/login` | Login JWT |
| POST | `/api/auth/register` | Registro |
| GET | `/api/cameras` | Listar câmeras |
| POST | `/api/cameras` | Criar câmera |
| POST | `/api/v1/videos/upload-url` | Presigned URL para upload |
| GET | `/api/training/videos/{id}/frames` | Frames para anotação |
| POST | `/api/training/frames/{id}/annotations` | Salvar anotações |
| GET | `/api/v1/storage/health` | Health do R2 |
| GET | `/health` | Health geral |
| GET | `/api/v1/docs` | Swagger UI |

---

## Estrutura do Projeto

```
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Blueprints Flask por domínio
│   │   ├── core/            # auth, exceptions, responses, validators
│   │   ├── domain/services/ # Lógica de negócio
│   │   └── infrastructure/  # DB, storage, queue
│   ├── scripts/
│   │   ├── rtsp_simulator.py  # Simulador RTSP local
│   │   └── test_videos/       # Vídeos de teste (git-ignored)
│   └── tests/               # 316 testes, 80%+ coverage
├── frontend/src/
│   ├── components/
│   │   └── AnnotationInterface.jsx  # ← CONGELADO — não modificar
│   ├── hooks/
│   └── services/
├── worker/
│   └── worker_server.py     # Worker Redis pub/sub (FFmpeg + YOLO)
├── services/shared/
│   └── events.py            # EventPublisher / EventConsumer
├── migrations/              # SQL idempotentes (numeradas)
└── docs/                    # Arquitetura e decisões
```

---

## Convenções

- Commits: Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`)
- Branches: `staging` → pré-produção | `main` → produção (apenas via PR)
- Never push directly to `main`
- Testes: `cd backend && python -m pytest`
