# Task 069 — Unificação do contrato frontend↔backend (mapa canônico + ADR de estado-alvo)

**Status**: FASE 1 CONCLUÍDA (2026-07-12) — ver `docs/API_CONTRACT_MAP.md` + ADR-0041 (Proposta). Fase 2 é gate humano, não executada.
**Risk**: P2-MÉDIO na Fase 1 (auditoria/documentação, zero mudança de comportamento) · P0-CRÍTICO na Fase 2 (toca convenção de rota + build — GATE HUMANO, só executar após aprovar o ADR)
**Branch**: agent/task-069-api-contract-map (a partir de develop)

## Contexto

Não existe contrato único e canônico frontend↔backend. Está implícito e espalhado:
- Frontend: `apps/frontend/src/services/*.ts` (api.ts centraliza HTTP) + `apps/frontend/src/types/` (interfaces TS **manuais**).
- Backend: blueprints em `services/api/app/api/` sob DUAS famílias — `/api/*` (legado) e `/api/v1/*` (novo).
- Specs formais existentes: `shared/proto/edge-openapi.yaml` (Edge↔Nuvem, não FE↔BE) e ADR-0037 (só pipeline de treino).

Histórico: tipos TS manuais já causaram bug de **drift** (front esperando campo que o backend renomeou). Não há geração de tipos nem contract test.

## Fase 1 — EXECUTAR (auditoria + mapa canônico; zero mudança de comportamento)

1. Auditar todo blueprint em `services/api/app/api/` (v1 + legado): método, path completo, auth (JWT/papel/tenant), request, envelope `{status,data}`, códigos de erro.
2. Cruzar com todo consumidor no front (`services/*.ts` + `types/`): qual endpoint cada service chama, qual tipo TS mapeia qual response.
3. Produzir `docs/API_CONTRACT_MAP.md` — mapa vivo por domínio (endpoint → método → auth → request → response(envelope+tipo) → service FE → tipo TS).
4. Tabela de divergências: (a) FE chama endpoint inexistente/renomeado; (b) mismatch de tipo; (c) endpoints sem consumidor (morto); (d) duplicata de versão `/api` × `/api/v1`; (e) placeholders (`my_domain`, `my_feature`, `{domain}`).
5. NÃO corrigir comportamento — só documentar + severidade sugerida.

## Fase 2 — PROPOR EM ADR (não executar sem aprovação)

ADR (próximo nº livre; 0040 reservado p/ edge/Jetson não-mergeada → usar 0041+) propondo:
- Convergir tudo para `/api/v1` (deprecar `/api/*`), plano sem breaking abrupto.
- OpenAPI do backend como fonte da verdade (estendendo o padrão do edge-openapi.yaml) + geração de tipos TS + contract test no CI.
- Remover placeholders.

## Aceite

- `docs/API_CONTRACT_MAP.md` com mapa + tabela de divergências.
- ADR de Fase 2 (status Proposta).
- Resumo dos achados graves (drift real, endpoints mortos, duplicatas).
- STOP para revisão humana antes de qualquer correção de código ou execução da Fase 2.

## Relaciona

ADR-0037 (contrato treino), task-057 (auditoria operabilidade FE↔BE), edge-openapi.yaml.

## Execução (Fase 1) — 2026-07-12

- `docs/API_CONTRACT_MAP.md` produzido via levantamento automatizado (9 agentes lendo os 32 arquivos de blueprint + 9 arquivos de services/types do frontend, branch `develop`), curado e cruzado com `docs/quality/CONTRATO_FRONT_BACK.md` (operabilidade, já existente — não duplicado).
- `docs/decisions/adr/0041-api-contract-convergence.md` criado com status **Proposta** (Fase 2, gate humano — não executar sem aprovação explícita).
- 15 achados graves no resumo executivo, incluindo **vulnerabilidades de segurança reais fora do escopo original desta task** (cross-tenant em `/api/alerts/<id>/snapshot`, `/api/v1/verification/queue*`, `/api/modules/<code>/classes/<id>` sem tenant/role, e `/api/v1/quality/demo/seed?force=true` capaz de apagar dados reais de produção) — reportadas para triagem humana separada, **não corrigidas aqui** (Fase 1 é auditoria pura, zero mudança de comportamento).
- Zero mudança de comportamento de código nesta task.
