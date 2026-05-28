# Open Questions — Recognition Platform

Questões que requerem decisão de Vitor antes de executar.
Respostas completas em `docs/decisions/oq-responses.md`.

---

## OQ-001 — Chat/Assistant Feature ✅ RESPONDIDA (decisão futura)

**Status:** Mantida experimental. Não bloqueia edge deployment.
**Decisão (2026-05-27):** Opção A — preservar como feature experimental. Nenhum refactor de edge deve quebrar `/api/chat`, `ChatFAB`, `assistant_docs` ou migration pgvector.
**Próxima ação:** Nenhuma. Roadmap a decidir em sprint futura.

---

## OQ-002 — Conteúdo de painel-adm/ além dos 6 serviços ⏳ PENDENTE (Pre-4)

**Status:** Bloqueante para Fase 0. Pre-4 investigation task criada.
**Contexto:** `painel-adm/` contém além dos 6 microsserviços: `backend/`, `frontend/`, `migrations/`, `pre-annotation-service/`, `agent/`, `landing-page/`. São cópias? Versões antigas? Código divergente?
**Próxima ação:** Claude executa Pre-4 (investigação com diff, git log do sub-repo), documenta em `docs/decisions/painel-adm-investigation.md`, PARA e aguarda decisão de Vitor por diretório (ARCHIVE / DELETE / MERGE).

---

## OQ-003 — Tasks EDGE durante migração ✅ RESPONDIDA

**Status:** Resolvida. Ver ADR-0013.
**Decisão final (2026-05-27):** Cutover direto na Fase 3. Sem shadow mode. Tasks EDGE permanecem no cloud Celery durante Fases 0–2, migradas para services/inference/ na Fase 3 sem período de coexistência. Recognition é greenfield (zero clientes em produção).
**Artefatos criados:** ADR-0013 (direct-cutover-no-shadow).

---

## OQ-004 — `models` vs `trained_models` como tabela canônica ✅ RESPONDIDA

**Status:** Resolvida. Ver ADR-0012.
**Decisão (2026-05-27):** `models` é a tabela canônica. `trained_models` permanece legacy. Bug fix em `quality_inference.py:90` é Pre-1.

---

## OQ-006 — Estratégia para serviços removidos de staging na Fase 3 ⏳ PENDENTE

**Status:** Aguarda decisão de Vitor. Não bloqueia PR #3 (só documenta).
Bloqueia início da Fase 3.

**Contexto:** Os serviços `camera-gateway`, `ws-gateway`, `training-service`,
`auth-service`, `scheduler-service` e `pre-annotation-service` foram removidos
de staging em maio/2026 (absorvidos pelo monolito api-v3). Estão preservados
na tag `archive/microservices-attempt-1`. A Fase 3 precisa recriar
`services/camera-gateway/` e `services/training/` para edge deployment.

**Opções:**
- **A) Reescrever do zero** — ignorar o código da tag; criar serviços novos
- **B) Portar da tag** — usar `archive/microservices-attempt-1` como ponto de
  partida, adaptando para multi-tenancy e logging do monorepo
- **C) Híbrido** — PORTAR `camera-gateway` e `training-service`; DESCARTAR os demais

**Análise disponível:**
- `docs/decisions/painel-adm-code-value-assessment.md` — avaliação por serviço
- `docs/decisions/inference-migration-feasibility.md` — análise do inference-service
- Recomendação: Opção C (PORTAR camera-gateway e training-service; o resto já está
  em api-v3 ou é descartável)

**Próxima ação:** Decisão de Vitor. Após aprovada, registrar em `docs/decisions/oq-responses.md`.

---

## OQ-005 — Branch base ✅ RESPONDIDA

**Status:** Resolvida.
**Decisão (2026-05-27):** `develop` criada a partir de `staging`. Fluxo: `feature/*` → `develop` (PR) → `staging` → `main`. Pré-flight em `feature/preflight-fixes`. Fase 0 em `feature/phase-0-reorg`.
