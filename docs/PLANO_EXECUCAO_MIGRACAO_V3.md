# Plano de Execução — Segurança → Main → Contrato → Migração v3 → Main

> **Sequência definida pelo Vitor (2026-07-12).** Cada fase tem um GATE humano antes de avançar.
> Regra transversal: nada vai pra `main` sem estar verde e revisado; merge `develop→main` sempre
> **merge commit** (preserva autoria/gráfico de contribuições — runbook GITHUB_CONTRIBUTIONS_MERGE_MAIN.md).

## Visão geral (ordem)

`[1] Correções + merges` → `[2] Merge main #1 (segurança)` → `[3] Validar contrato FE↔BE` →
`[4] Migração do front novo em develop` → `[5] Validação final (inclui fluxo de treino)` →
`[6] Merge main #2 (cutover v3)`

---

## Fase 1 — Correções (segurança) + merge dos PRs abertos

**O quê:** mergear os 5 PRs abertos e corrigir as 5 vulnerabilidades de produção.
- PRs: #135 (task-045, vuln modelo cross-tenant), #137 (task-057, P0 fueling + quick-wins), #134
  (task-058), #139 (task-039), #136 (task-040).
- Vulns: task-072 (seed destrutivo #5), 073 (módulos/classes tenant_id #6), 074 (alerts/snapshot #7),
  075 (verificação tenant_id #14), 076 (senha previsível #4).
- Cada correção: 1 PR, teste falha-antes/passa-depois, security-review, `--merge`.

**Gate 1:** develop verde (CI Actions), 10 merges confirmados, author-check rodado.

## Fase 2 — Patch de produção + branch estável

> **Correção importante:** produção = **staging** (auto-deploy Railway), NÃO main. Então:
- **`develop→staging`** (merge commit) = **o que patcha produção** — sobe as 7 correções de segurança pro ar.
- **`develop→main`** (merge commit) = branch estável + gráfico de contribuições (não é produção).
- **Adiado ("tratar staging depois"):** portar pra develop os 39 commits órfãos de staging que forem
  **únicos** (descartar os duplicados de develop). A lista dos 39 é gerada agora, a decisão vem depois.

**Gate 2:** deploy Railway verde na **staging** (produção com as vulnerabilidades **corrigidas**); main
atualizada. Isto **limpa a Fase G de segurança** da migração (task-071).

## Fase 3 — Validar o contrato frontend↔backend

**O quê:** revalidar o contrato **após** as correções (as rotas mudaram — tenant_id/gates novos), e
fechar os pontos cegos:
- Já existe: `API_CONTRACT_MAP.md`, `CONTRATO_FRONT_BACK.md`, `CONTRACT_COVERAGE_VALIDATION.md`
  (cobertura 61% ok / 22% consertar / 17% falta).
- Falta fechar (Fase G da task-071): **enumerar o domínio Quality** (50 rotas, ponto cego),
  **confirmar Fueling→Contagem**, **decidir os 4 "FALTA que bloqueia"** (Validação de Contagem, clipes
  de evidência, pré-anotação, verificação segura), **consolidar uploads** (`/api/v1/videos/*`).
- Re-rodar a validação de cobertura pra refletir as rotas corrigidas.

**Gate 3:** contrato revalidado; cada divergência PARCIAL com conserto definido; cada FALTA com decisão
(backend novo OU "em breve"). Sem ponto cego.

## Fase 4 — Migração do novo front para develop

**O quê:** executar a task-071 (multi-PR, STOP-for-review por fase), **EPI primeiro** (maior cobertura,
go-live RVB):
- Fase 0 andaime (task-070) → 1 Auth → 2 Shell+Monitoramento+Dashboard → 3 Câmeras+wizards →
  4 Alertas+Investigação → 5 Modelos+**Training Studio**+Bridge → 6 Admin+Relatórios →
  7 (pós-Quality) Contagem/Validação/Peças/Retrabalho/Verificação/Kiosk.
- Regra de correção em cada tela: COBERTO→portar; PARCIAL→consertar (envelope/path/dono); FALTA→"em breve".
- Tudo em develop, atrás da flag `ui_v3` (OFF em prod até o cutover).

**Gate 4:** telas EPI migradas, `tsc` limpo, guard-rail de cores verde, paridade por tela.

## Fase 5 — Validação final (paridade + fluxo de treino completo)

**O quê:** provar que o front novo **funciona igual ou melhor** que o atual, antes do cutover:
1. **Paridade por tela:** cada endpoint que o front atual chama com sucesso responde igual no novo.
2. **FLUXO DE TREINAMENTO COMPLETO presente e funcional** (requisito explícito) — o Training Studio do
   front novo tem que cobrir TODO o pipeline que construímos (PRs Fase A/B/C + compute providers):
   coleta de dados (câmera/NVR/upload/vídeo) → active learning → pré-anotação (flag) → anotação/HITL →
   versionamento de dataset (COCO) → treino (compute_target: nuvem/edge/local) → campeão×desafiante →
   deploy/model-config por câmera → drift monitor → registry/linhagem. Rodar um E2E de treino pelo
   front novo (como a Fase A, com fallback local se sem VAST_API_KEY) e confirmar cada estágio na UI.
3. Sem raw fetch novo; nenhuma chamada a endpoint morto; nenhum P0 reintroduzido.

**Gate 5:** checklist de paridade + E2E de treino verde pela UI nova. Cutover autorizado.

## Fase 6 — Merge para a main #2 (cutover v3)

**O quê:** v3 vira default, remove shell antigo + temas professional/cyberpunk (white-label preservado).
Promover `develop→main` (merge commit). PARAR pro go do Vitor antes do push.

**Gate 6:** produção no front v3, fluxo de treino validado, contribuições preservadas.

---

## Índice de artefatos

- Correções: task-072..076 · PRs #134-#139.
- Contrato: docs/API_CONTRACT_MAP.md · docs/quality/CONTRATO_FRONT_BACK.md ·
  docs/design/recognition-v3/CONTRACT_COVERAGE_VALIDATION.md · MIGRATION_WIRING_SPEC.md.
- Migração: docs/decisions/adr/0041-* · task-070 (andaime) · task-071 (telas+correções).
- Main: docs/runbooks/GITHUB_CONTRIBUTIONS_MERGE_MAIN.md.
- Design (fonte única): docs/design/recognition-v3/Recognition-visao-final.dc.html.

## Gates humanos (resumo)

1 (segurança verde) → **main #1** → 3 (contrato revalidado) → 4 (EPI migrado) →
5 (paridade + treino E2E) → **main #2 (cutover)**. Nenhum salto de gate.
