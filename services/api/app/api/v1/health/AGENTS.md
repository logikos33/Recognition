<!-- Parent: ../AGENTS.md -->

# health — System Health Checks

Database and Redis connectivity checks for Railway healthcheck. Ver também
`docs/runbooks/SINAIS_DEGRADACAO.md` (fallbacks sobreviventes do sistema e seus sinais).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health legado (também em `/api/v1/health`) — **inalterado**, é o que o Railway usa hoje |
| `/livez` | GET | Liveness — processo vivo. NUNCA toca DB/Redis/R2. Sempre 200. |
| `/readyz` | GET | Readiness — única barreira contra promover deploy degradado (item 2.3). Lê cache de fundo (`readiness.py`), nunca toca dependência direto. |
| `/status` | GET | Diagnóstico rico (latências, cache de readiness) — **nunca** consumido por automação que reinicia |
| `/api/v1/health/metrics` | GET (JWT) | Métricas pro footer global |

**Key Notes — `/health` (legado, não mudar sem plano de rollout):**
- No JWT required — used by Railway healthcheck
- Returns 200 if DB OK (even if Redis degraded)
- Returns 503 if database unavailable
- Checks: database (SELECT 1), redis (PING)
- Never exposes connection strings or internal details

**Key Notes — `/readyz` (`readiness.py`):**
- Invariantes determinísticos (`worker_class`: gevent ausente com `SERVICE_TYPE=api`;
  `storage_backend`: local sem `ALLOW_EPHEMERAL_STORAGE=1`) reprovam DURO, sem retry.
- Dependências transitórias (DB, Redis) só reprovam após `FAILURE_THRESHOLD` (3) falhas
  consecutivas do refresher de fundo — backoff, não flipa na primeira piscada.
- Cache atualizado por um greenlet gevent (`ReadinessCache.start_background_refresh`,
  chamado em `create_app` quando `not TESTING`) a cada `REFRESH_INTERVAL_SECONDS` (10s).
  Fallback pra thread daemon se gevent não importar. Em TESTING não roda em background —
  `/readyz` faz bootstrap on-demand na 1ª leitura (mesmo `refresh()`).
- Cache com mais de `STALE_AFTER_SECONDS` (30s) sem atualizar → 503 + `stale: true`, mesmo
  que o conteúdo cacheado diga "ready" (fail closed).
- Rollout: apontar o Healthcheck Path do Railway pra `/readyz` só DEPOIS do merge (ver
  runbook de sinais de degradação).
