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

## OQ-008 — Tabelas de edge (042-045): public ou tenant_schema? ✅ RESOLVIDA

**Status:** Resolvida (2026-05-28). Ver ADR-0016.
**Decisão:** Opção C (Híbrido) — tabelas de controle de edge em `public` com `tenant_id NOT NULL`;
`site_id` adicionado via ALTER TABLE simples nas tabelas public, via loop EXECUTE format nas
tabelas tenant_schema (`quality_inspections`).

**Regra de roteamento final:**

| Tabela | Localização | Como adicionar site_id |
|--------|------------|----------------------|
| `edge_sites`, `device_tokens` | NEW — public com `tenant_id NOT NULL` | Novas tabelas (migration 042/043) |
| `ip_cameras` | public (tem tenant_id) | `ALTER TABLE` simples |
| `alerts` | public (tem tenant_id) | `ALTER TABLE` simples |
| `counting_events` | public | `ALTER TABLE` simples |
| `operations` | public (tem tenant_id) | `ALTER TABLE` simples |
| `quality_inspections` | tenant_schema ONLY | Loop `EXECUTE format` sobre `tenants.slug` + atualizar `create_tenant_schema()` |
| `camera_events` | public (dead code) | **Ignorar** — tabela não usada |

**3 ambiguidades resolvidas durante investigação:**
1. `camera_events` — dead code; detecções vão para `public.alerts`
2. `alerts` canônica — `public.alerts` (com `tenant_id`); `tenant_schema.alerts` é dead code
3. Iteração sobre schemas — `SELECT slug FROM public.tenants WHERE is_active = true`

**Artefatos:** ADR-0016, `docs/decisions/multi-tenancy-investigation.md` §7
**Próxima ação:** Escrever migrations 042-045 conforme ADR-0016.

---


## OQ-007 — Engine de inferência na Fase 3 ✅ RESPONDIDA

**Status:** Respondida (2026-05-27). Multi-backend desde Fase 3.
**Decisão:** `INFERENCE_ENGINE=deepstream` em produção edge; `INFERENCE_ENGINE=ultralytics`
em dev/CI/staging. Mesma interface Redis pub/sub. Ver ADR-0015.

---

## OQ-006 — Estratégia para serviços removidos de staging na Fase 3 ✅ RESPONDIDA

**Status:** Respondida (2026-05-27). Referência pura — consultar só camera-gateway
e ws-gateway. Demais serviços: ARCHIVE sem consulta.
**Decisão completa:** Ver `docs/decisions/oq-responses.md` seção OQ-006.

---

## OQ-005 — Branch base ✅ RESPONDIDA

**Status:** Resolvida.
**Decisão (2026-05-27):** `develop` criada a partir de `staging`. Fluxo: `feature/*` → `develop` (PR) → `staging` → `main`. Pré-flight em `feature/preflight-fixes`. Fase 0 em `feature/phase-0-reorg`.
