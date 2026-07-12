# Estado dos Testes + Roadmap Priorizado

**Data:** 2026-06-24 · Base pra fila de validação no ambiente de DEV antes de homologação.
> Cobertura POR MÓDULO precisa de um `pytest --cov=app --cov-report=term-missing` no dev pra números
> exatos — abaixo, o que é fato (contagens/arquivos) + os gaps conhecidos.

## 1. O que JÁ existe e passa (estado atual)
- **Backend:** 131 arquivos de teste, **2370 testes**, todos verdes. Gate **60%** (cobertura ~61%).
  **0 `--deselect`** no CI (os 11 testes antes desligados foram REABILITADOS). Só **2 skip/xfail**.
- **Segurança (tests/security/):** isolamento por tenant (`test_alert_repo_tenant_isolation`,
  `test_counting_repo_tenant_isolation`, `test_frame_repo_owner_isolation`, `test_counting_sessions_tenant`,
  `test_tenant_isolation`), SSRF/edge (`test_edge_invariants`), **`test_set_search_path`** (relevante
  pro PgBouncer), `test_edge_schema`, `test_default_tenant_deactivated`, `test_fueling_endpoints`,
  `test_health_metrics`, `test_migration_050_loading_fields`. → os testes de regressão dos P0 de
  vazamento cross-tenant EXISTEM.
- **Harness:** migrations (D1 pass1/pass2/pytest) + cenários (baseline + isolation) com device_sim.
- **Frontend:** 8 arquivos (vitest/playwright) — cobertura **fina**.

## 2. Testes ABERTOS / faltando (gap)
| Item | Tipo | Prioridade |
|---|---|---|
| 2 `skip/xfail` — identificar quais e por quê (não esconder débito) | FIX | AGORA |
| Teste de ESCALA 4→28 câmeras (task-052) — não existe; revela o teto de conexão | FIX/validação | AGORA |
| Testes do ONNX Detector Factory (task-055b) — criar junto da feature | FIX | AGORA |
| Testes das features novas (deliverable c linha-de-cruzamento; 058 integrações: cifra/mascaramento/isolamento) | FIX (DoD) | AGORA |
| `set_search_path` sob **transaction pooling** (PgBouncer) — cenário além da sessão | FIX | com 053 |
| Cobertura baixa: `quality_training`, `operations` (registry/canonicals), `validation_handlers`, `versioning`, training dispatch | MELHORIA | DEPOIS |
| E2E/Playwright fino (8) — jornadas (criar modelo, VMS, onboarding, treino) | MELHORIA (jornadas críticas = agora) | DEPOIS |
| Teste de performance da tela VMS sob carga (não travar 4→28) | MELHORIA/validação | DEPOIS |

## 3. Débito técnico a VALIDAR (ficou pra trás?)
- **`BaseRepository._execute` usa `conn.cursor()` SEM fechar** → possível vazamento de cursor. É a base
  de TODO o código e **pesa exatamente no PgBouncer/escala** — validar e, se confirmado, corrigir (usar
  cursor gerenciado). Prioridade alta antes da 053.
- **Confirmar os P0 cross-tenant** (frame `get_annotated_by_video`, `count_validated`, alert
  `list_with_filters`, counting `get_session`) têm regressão FALHA-antes/PASSA-depois de verdade (os
  arquivos existem — verificar as asserções do `WHERE tenant_id`).
- **eventlet→gevent** (deprecação do gunicorn) — validar se ainda usa eventlet; migrar antes do upgrade.
- **`_dispatch_vast_ai` é simulação** → resolvido pela task-054 (treino real).
- **Os 2 skip/xfail** — decidir corrigir ou documentar.

## 4. Priorização
**AGORA (fix/licença/validação — antes de staging):**
1. **055b — ONNX Detector Factory** (+ testes): remove a AGPL do caminho (licença nº1).
2. **052 — escala 4→28** (+ teste): mede o teto de conexão → decide 053.
3. Identificar/resolver os **2 skip/xfail**.
4. Testes das features novas conforme entram (deliverable c, 058) — parte do Definition of Done.
5. **Validar o cursor-close do BaseRepository** (débito que morde a escala).

**DEPOIS (melhoria — não bloqueia go-live):**
- 053 PgBouncer + teste de `set_search_path` em transaction pooling.
- Subir cobertura dos módulos baixos (quality_training, operations, versioning, validation_handlers) — meta 70%+.
- Expandir E2E/Playwright das jornadas do leigo.
- Teste de performance da VMS sob carga.
- eventlet→gevent.

**FIXO × MELHORIA:** FIX = quebra / segurança / licença / débito que morde a escala (prioridade agora).
MELHORIA = cobertura / robustez / performance que eleva qualidade mas não bloqueia o go-live.

## 5. Fila de validação no ambiente de DEV (antes de homologação)
- [ ] Suíte completa verde no dev: ruff + pytest (cov ≥60) + tsc + vitest + playwright + harness migrations.
- [ ] `pytest --cov-report=term-missing` no dev → preencher a cobertura POR MÓDULO (fecha o item da seção 1).
- [ ] Validar pela UI (operável por leigo): criar modelo (linha de cruzamento), VMS ao vivo,
      onboarding de câmera, ambiente de treino, integrações (058), console de teste.
- [ ] Rodar o harness de escala 4→28 → registrar o ponto de degradação (evidência pra 053).
- [ ] Migrations no boot 2x (idempotência) OK.
- [ ] Débito validado: cursor-close, P0 de tenant, skip/xfail.
