# Fase 0 + A + B — Deploy Success Report

**Data:** 2026-05-28  
**Branch:** staging  
**SHA final:** e48012d (worker fix)

---

## Cronologia

| Etapa | Descrição | SHA / Resultado |
|-------|-----------|-----------------|
| Fase 0 (PR #5) | Reorganização monorepo: `backend/` → `services/api/`, `frontend/` → `apps/frontend/`, `landing-page/` → `apps/landing/` | develop mergeado |
| Fase A (PR #6) | Limpeza Railway config: delete `railway.toml` raiz, fix `worker-railway.toml`, fix `Dockerfile.worker` COPY paths, limpeza git leaks (48 YOLO labels + build outputs), `.gitignore` atualizado | cc560e4 mergeado |
| Fase B | 5 mudanças manuais no Railway Dashboard: `rootDirectory` + `configFile` para 4 serviços (API-V3, Frontend, landing-page, celery-worker) | Manual |
| Merge develop → staging | Push dispara 4 deploys Railway | b663ebe |
| Resultado inicial | 3/4 verde — API-V3 com 2 builds FAILED por `-k eventlet` stale no `startCommand` | FAILED ×2 |
| Fix worker (e48012d) | Remove `startCommand` override do `railway.toml` + atualiza `railway_start.py` para `GeventWebSocketWorker` | SUCCESS |
| **Resultado final** | **4/4 serviços verdes** | ✅ |

---

## Estado Final dos Serviços

| Serviço | URL produção | Worker | Source no repo |
|---------|-------------|--------|----------------|
| API-V3 | `api-v3-production-2b22.up.railway.app` | `GeventWebSocketWorker` | `services/api/` |
| Frontend | `frontend-production-bf96.up.railway.app` | nginx (Vite build) | `apps/frontend/` |
| landing-page | `landing-page-production-b659.up.railway.app` | Astro static | `apps/landing/` |
| celery-worker | (interno, sem URL pública) | Celery prefork | root via `worker-railway.toml` |

**Healthcheck API-V3 pós-deploy:**
```json
{"checks":{"database":true,"redis":true},"status":"healthy"}
```

---

## Causa Raiz do Falha Inicial (API-V3)

Commit `ff3a4ca` (`fix(api): migrar eventlet → gevent`) substituiu `eventlet>=0.35.0` por `gevent>=24.2.0 + gevent-websocket>=0.10.1` em `requirements/base.txt`, mas **não atualizou** o `startCommand` em `services/api/railway.toml`. O `startCommand` com `-k eventlet` sobrescrevia o Dockerfile `CMD` e chamava gunicorn diretamente, sem passar por `railway_start.py`. Como eventlet não estava mais instalado, o container crashava no startup em loop.

---

## Aprendizados

1. **`startCommand` bypassa `railway_start.py` inteiramente.** Sem ele, `CMD ["python3", "railway_start.py"]` do Dockerfile roda — executando migrations, DB check e admin creation antes do gunicorn.

2. **Mudanças em `requirements/` exigem checklist de `railway.toml`.** Se um worker/package é removido de requirements, qualquer referência a ele em `startCommand` vira bug silencioso até o próximo deploy.

3. **Flask-SocketIO com `async_mode='gevent'` requer `GeventWebSocketWorker`**, não plain `-k gevent`. Sem o worker correto, WebSocket upgrades podem falhar silenciosamente (conexões caem para long-polling).

4. **Railway blue/green protege produção.** O container de 2026-05-08 (buildado quando eventlet ainda estava em requirements) continuou servindo tráfego durante os 3 builds FAILED, sem interrupção para os usuários.

5. **`rootDirectory` no Railway é inferido da localização do `railway.toml`** quando não definido explicitamente no Dashboard. Isso define o Docker build context — causa raiz de builds que falham com `COPY requirements/` quando o `rootDirectory` é um subdiretório.

---

## PENDs Ativos

Ver `docs/runbooks/phase-0-issues.md` para lista completa:

- PEND-001: Docker build local não validado
- PEND-002: 11 testes pré-existentes baselinados
- PEND-003: 319 erros ruff baselinados
- PEND-004: `railway_start.py` na raiz (por design)
- PEND-005: `services/api/migrations/` vazio mas existe
- PEND-006: Worker requirements instala CUDA completo (~2.5 GB)
- PEND-007: `ON CONFLICT (git_sha)` sem constraint correspondente — auto-versionamento quebrado silenciosamente

**Próxima Fase:** Fase 1 — migrations 042-045 + `recognition_shared`. Corrigir PEND-007 antes de iniciar.
