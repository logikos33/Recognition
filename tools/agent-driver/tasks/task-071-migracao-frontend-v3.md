# Task 071 — Migração do frontend v3 "Centro de Comando" (com correções do contrato)

**Status**: PENDING — PARQUEADA (rodar após as execuções em curso no Claude Code; PR-5 etc.).
**NÃO é fila autônoma:** é fluxo multi-PR com STOP-for-review entre cada fase (igual à pipeline de treino).
**Risk**: P0-CRÍTICO (troca de shell/telas do produto; toca auth, tenant-isolation, todos os domínios).
**Branch base**: worktree a partir de origin/develop (NUNCA no checkout wip/*). Um passo = um branch = um PR.
**Relaciona**: ADR-0041 (migração v3), MIGRATION_WIRING_SPEC.md, CONTRACT_COVERAGE_VALIDATION.md,
API_CONTRACT_MAP.md, task-070 (andaime Fase 0).

## Objetivo

Migrar o produto pro design v3 (`docs/design/recognition-v3/Recognition-visao-final.dc.html`) de forma
que **o que funciona hoje continue funcionando** e o que está com drift seja **consertado**, não
replicado. Cobertura medida: **61% COBERTO, 22% PARCIAL, 17% FALTA** (ver CONTRACT_COVERAGE_VALIDATION.md).

## Fontes de verdade (ler antes)
- Design: `docs/design/recognition-v3/Recognition-visao-final.dc.html` (+ support.js, screenshots/).
- Fiação: `docs/design/recognition-v3/MIGRATION_WIRING_SPEC.md` (tela→endpoints).
- Cobertura/gaps: `docs/design/recognition-v3/CONTRACT_COVERAGE_VALIDATION.md`.
- Contrato: `docs/API_CONTRACT_MAP.md` + `docs/quality/CONTRATO_FRONT_BACK.md`.

## Regras de correção (aplicar em TODA tela migrada)

1. **Envelope `{status,data}`** — corrigir onde o service atual assume `{success,message,data}`:
   `eventsService` (Dashboard por classe/câmera, Investigação) e `impersonation.ts` (achado #3).
2. **Path real por rota** — NÃO presumir `/api/v1`; em Câmeras só `probe/effective-model/config/
   health-context` têm alias v1 (#12). Usar o path que o mapa marca como real.
3. **Sempre `api.ts`, zero raw fetch** — portar Anotação, Auditoria-export e Andon (que hoje usam
   `fetch()` cru) para o wrapper.
4. **Endpoint morto/inexistente ⇒ UI "em breve" + pendência**, nunca chamada fabricada: Counting
   `updateSession`/`validation-report` (#1/#2), Frames `pre-annotate` (blueprint vazio #9).
5. **Dono correto de rota duplicada** — `acknowledge` no `alerts`, não no delegado de training (#11);
   branding só o canônico `/api/v1/admin/tenants/<id>/branding`, não o deprecated (#10).
6. **Não surfar bug P0 de segurança** — não exibir/depender de: snapshot sem tenant_id (#7), toggle de
   classe cross-tenant (#6), verificação sem tenant_id (#14), `quality/demo/seed` destrutivo (#5),
   `temp_password` previsível (#4), `storage/health` público (#15). Ver Fase G (viram issues).
7. **Export de Relatórios** usar `GET /api/v1/reports/export` (o atual chama sem `/api` → 404, D3).
8. **Uploads** — fiar num pipeline só (recomendado `/api/v1/videos/*`), aposentar `/api/training/videos`
   (#13) — confirmar na Fase G.

## Fase G — GATE (pré-migração; destrava as inconsistências)

Rodar/decidir ANTES das fases de tela. Cada item é um PR ou uma issue própria:
1. **Enumerar o domínio Quality** (`quality/routes.py`, 50 rotas não mapeadas) e completar a cobertura
   de Peças/Retrabalho/Kiosk/Andon — hoje é ponto cego. (Paralelo se o go-live for só EPI.)
2. **Confirmar Fueling→Contagem** — o "Carga & Descarga" do design é `counting`, não `fueling`; decidir
   se fueling foi absorvido (senão as 5 rotas ficam órfãs).
3. **Decidir os 4 "FALTA que bloqueia"** (cada um: backend novo via ADR/task OU UI "em breve"):
   Validação de Contagem (aceite/rejeição/agregado/threshold), clipes de evidência ~20s (ADR-0033),
   pré-anotação IA (flag OFF — "em breve"), verificação segura (depende do fix #14).
4. **Abrir issues dos P0 de segurança** (#4,#5,#6,#7,#14,#15) — priorizar antes de migrar as telas que
   os tocam (Alertas, Modelos, Verificação, Admin, Quality).
5. **Confirmar consolidação de uploads** (#13).

## Fases de tela (ordem: EPI primeiro — maior cobertura, go-live RVB)

Cada fase = 1 PR pra develop + STOP-for-review (revisão visual + paridade). Portar reusando
`components/ui/*`; recriar pixel-perfect; aplicar as Regras de Correção acima.

- **Fase 0** — Andaime (task-070): flag `ui_v3`, shell, tema real, ⌘K casca. *(pré-requisito)*
- **Fase 1** — Auth: Boot, Login, Module Select.
- **Fase 2** — App Shell + Monitoramento (VMS grid) + Dashboard.
- **Fase 3** — Câmeras + Camera Wizard + Scenario/ROI Editor + Operação/Operation Wizard.
- **Fase 4** — Alertas + Alert Detail Drawer + Investigação.
- **Fase 5** — Modelos & Classes + Training Studio (7 estágios, canvas @dnd-kit) + Model↔Camera Bridge.
- **Fase 6** — Admin (19 abas) + Tenant Detail + Relatórios.
- **Fase 7 (pós-gate Quality)** — Contagem + Validação + Peças + Retrabalho + Verificação + Kiosk/Andon.
- **Cutover** — v3 default, remove shell antigo + temas professional/cyberpunk (white-label preservado).

## Aceite (por fase) — "funciona igual"

- Cada endpoint que o front atual chama com sucesso responde igual no novo (mesma resposta/comportamento).
- Toda divergência PARCIAL da fase foi **consertada** (envelope/path/dono), com teste onde aplicável.
- Todo item FALTA da fase está como "em breve" + pendência registrada (não chamada fabricada).
- `npx tsc --noEmit` limpo; guard-rail de cores (task-065) verde; sem novo raw fetch.
- STOP-for-review antes da próxima fase.
