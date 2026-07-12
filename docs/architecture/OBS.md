# OBS — Spec de Observabilidade (stub)

**Status:** RASCUNHO — implementação na Fase O1
**Data:** 2026-06-02

Ver implementação detalhada em:
`docs/architecture/HARNESS_PLANO_IMPLEMENTACAO.md § Fase O1` (linhas 43–60).

---

## O que medir

### Edge (via `public.edge_heartbeats`)

Tabela criada em `infra/migrations/053_edge_heartbeats.sql`. Cada heartbeat é um append
(`BIGSERIAL`) enviado pelo edge agent a cada N segundos.

| Métrica | Coluna | Unidade |
|---------|--------|---------|
| CPU | `cpu_pct` | % |
| Memória | `mem_pct` | % |
| GPU | `gpu_pct` | % (nullable) |
| Disco | `disk_pct` | % |
| FPS de inferência | `inference_fps` | frames/s |
| Latência média | `inference_latency_ms` | ms |
| Câmeras online | `cameras_online` | count |
| Câmeras total | `cameras_total` | count |
| Upload | `upload_kbps` | kbps |
| Download | `download_kbps` | kbps |
| Profundidade de fila | `queue_depth` | count |
| Versão do agente | `agent_version` | string |
| Status | `status` | enum |

### Cloud

| Métrica | Fonte | Alvo |
|---------|-------|------|
| Latência API p95 | logs gunicorn/nginx | < 500 ms |
| Throughput SocketIO | métricas Flask-SocketIO | — |
| Fila Celery | Redis (task queue depth) | — |
| Erro 5xx | Sentry | 0 em prod |

---

## Severidades

Alinhadas ao CHECK constraint de `edge_heartbeats.status` (migration 053):

| Status | Critério |
|--------|---------|
| `healthy` | Todos os recursos dentro do limite, FPS nominal |
| `degraded` | ≥ 1 recurso acima de threshold suave OU FPS < 80 % do nominal |
| `critical` | ≥ 1 recurso acima de threshold crítico OU FPS < 50 % |
| `offline` | Sem heartbeat há > N minutos (regra automática na API) |

---

## TODOs (Fase O1)

- [ ] Endpoint `POST /api/v1/edge/heartbeat` — ingest de heartbeats do edge agent.
- [ ] Painel admin "Sites & Saúde" — último heartbeat, status, FPS, câmeras online/total,
      GPU/CPU/disco, profundidade de fila, versão do edge.
- [ ] Regra automática "site offline": sem heartbeat há > N min → evento de saúde + alerta.
- [ ] Sentry plugado com `tags: {site_id, tenant_id, agent_version}`. Zero PII.
- [ ] Logs estruturados JSON (sem PII) em batch — não por evento.
- [ ] Definir thresholds de `degraded`/`critical` por classe de hardware.
