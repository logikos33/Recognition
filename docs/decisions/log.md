# Decision Log — Recognition Platform

Decisões menores tomadas durante diagnóstico e execução. Uma linha por decisão.
Decisões estruturais grandes → ADR em docs/decisions/adr/.

---

## 2026-05-27 — Diagnóstico inicial (pré-Fase 0)

- **MIGRATION NUMBERING:** Novas migrations de edge começam em 042 (não 013-016 como no plano) — 41 migrations já existem (001–041).
- **WORKER_REGISTRY vs EDGE_SITES:** Conceitos distintos. `worker_registry` armazena GPU workers físicos (tailscale_ip, gpu_model, vram). `edge_sites` armazenará sites de deployment físico. Manter ambos sem refatoração.
- **SYSTEM_VERSIONS sem conflito:** `system_versions` armazena checkpoints de configuração da plataforma (config_snapshot JSONB). `edge_version` vai em `edge_sites` conforme plano. Sem sobreposição.
- **AUTH-SERVICE DEPRECATED:** Frontend chama exclusivamente API-V3 (backend/) para login. auth-service em painel-adm/ não está integrado ao frontend e não suporta multi-tenant. Marcar como deprecated na Fase 0; não adicionar ao docker-compose.dev.yml.
- **FRAMES/ROUTES.PY = CÓDIGO MORTO:** Blueprint `frames_bp` existe mas tem zero endpoints implementados. Registrado em docs/decisions/initial-assessment.md. Não remove agora — pode ter uso futuro planejado.
- **ARQUITETURA DOCS INEXISTENTES:** `Arquitetura_Final_Recognition_RVB.md` e `Arquitetura_Inicial_Netbar.md` referenciados no plano Fase 0 não existem no repositório. Removidos da Fase 0. Arquivo existente `docs/EDGE_AGENT_ARCHITECTURE.md` move para `docs/architecture/`.
- **GITHUB ACTIONS = ZERO:** Não existe `.github/workflows/`. Deploy é via Railway push automático. CI/CD a criar do zero na Fase 0.
- **SITE_ID PURO ADITIVO:** Nenhuma das 8 tabelas que o plano propõe adicionar `site_id` tem essa coluna atualmente. Migrations 042–045 são puramente aditivas — baixo risco.
- **PAINEL-ADM .GIT ANINHADO:** `painel-adm/` tem `.git` interno. Requer Pre-4 (backup + remoção do .git) antes dos git mv da Fase 0. Ver ADR-0011.
- **CHAT/ASSISTANT EXPERIMENTAL:** Feature `/api/chat` + ChatFAB preservada como experimental. Fora do escopo do edge deployment. Refactors de edge NÃO devem quebrar essa feature. Roadmap a decidir em sprint futura. (OQ-001 respondida por Vitor 2026-05-27)
- **TASKS EDGE PERMANECEM NO CLOUD:** Durante Fases 0–5, as 6 tasks EDGE continuam rodando no cloud Celery. Shadow mode aprovado para Fase 6. Ver ADR-0013. (OQ-003 respondida por Vitor 2026-05-27)
- **`models` TABELA CANÔNICA:** Confirmado por Vitor. `models` é a tabela canônica para edge manifest e novos modelos. `trained_models` permanece como legacy sem remoção planejada neste deployment. (OQ-004 respondida por Vitor 2026-05-27)
- **BRANCH STRATEGY:** `develop` criada a partir de `staging`. Fluxo: `feature/*` → `develop` (PR) → `staging` (quando verde) → `main`. Branch pré-flight: `feature/preflight-fixes`. Branch Fase 0: `feature/phase-0-reorg`. (OQ-005 respondida por Vitor 2026-05-27)
- **BUG QUALITY_INFERENCE.PY:90:** Referência a tabela inexistente `training_models`. Deve ser `models`. Corrigido como Pre-1 antes da Fase 0.
- **MIGRATIONS 046-047 ADICIONADAS AO PLANO:** Migration 046 (`event_origin`) e 047 (`processing_mode`) adicionadas à Fase 1 para suportar shadow mode cutover. Ver ADR-0013.
