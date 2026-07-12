# ADR-0041 — Convergência do contrato frontend↔backend (`/api/v1` único + OpenAPI + tipos gerados)

**Status:** Proposta (2026-07-12) — **GATE HUMANO, não executar sem aprovação explícita.**
**Relaciona:** task-069 (Fase 1 — `docs/API_CONTRACT_MAP.md`), task-057 (auditoria de operabilidade —
`docs/quality/CONTRATO_FRONT_BACK.md`), ADR-0037 (contrato de API do pipeline de treino, mesmo
princípio aplicado só a um domínio), `shared/proto/edge-openapi.yaml` (padrão já existente
Edge↔Nuvem, reutilizável como referência de estrutura, não como contrato deste ADR).

## Contexto

`docs/API_CONTRACT_MAP.md` (Fase 1 da task-069, auditoria estática de 32 arquivos de blueprint ×
9 arquivos de services/types do frontend) confirmou empiricamente os sintomas descritos no
frontmatter da task-069:

- **Duas famílias de rota convivendo sem critério documentado**: a maioria dos blueprints mais
  antigos serve em `/api/*` (alerts, auth, cameras, chat, devices, frames, fueling, modules,
  reports, rules, streams, roles) enquanto os mais recentes usam `/api/v1/*` — e há blueprints
  **mistos** (ex.: `cameras/routes.py` é majoritariamente `/api` com só 4 rotas espelhadas em
  `/api/v1` como alias, criados reativamente para não cair num catch-all 405).
- **Duplicatas reais de rota/domínio**, não hipotéticas: duas APIs de branding paralelas (uma
  marcada `DEPRECATED` no próprio docstring mas ainda viva e roteável), `POST
  /api/alerts/<id>/acknowledge` registrado em dois blueprints diferentes, três pipelines de
  upload de vídeo/imagem de treino coexistindo.
- **Tipos TS manuais sem geração**: nenhum contrato formal liga `apps/frontend/src/types/*.ts`
  aos response shapes reais do backend — o mapa encontrou pelo menos um mismatch de envelope
  suspeito (`eventsService.ts` assumindo `{success,message,data}` onde o backend usa
  `{status,data}` de `app.core.responses`) e dois casos de frontend chamando endpoint que não
  existe (`countingService.updateSession`/`getValidationReport`).
- **Endpoints mortos ou nunca implementados**: blueprint `frames_bp` registrado sem nenhuma rota
  definida, apesar de `CLAUDE.md`/`AGENTS.md` documentarem `POST /api/frames/{id}/pre-annotate`
  como existente.

Nada disso foi corrigido na Fase 1 (auditoria pura, zero mudança de comportamento). Este ADR propõe
o que fazer a respeito — a decisão de **executar** é do humano revisor, não deste agente.

## Decisão proposta

### 1. `/api/v1` como única família de rota daqui pra frente

- Nenhuma rota nova nasce fora de `/api/v1/*`.
- Rotas legadas em `/api/*` recebem alias espelhado em `/api/v1/*` (mesmo handler, sem duplicar
  lógica) à medida que forem tocadas por outras tasks — **não** uma migração em massa de uma vez
  (evita o "big bang" que o próprio CLAUDE.md pede pra evitar em mudanças arriscadas).
- Prazo de descontinuação de `/api/*` a definir pelo humano (sugestão: sem prazo fixo até que o
  contract-test de OpenAPI, item 2, cubra 100% dos consumidores reais do frontend).

### 2. OpenAPI do backend como fonte da verdade

- Gerar OpenAPI a partir dos blueprints Flask existentes (ex.: `flask-smorest`/`apiflask` ou
  anotação manual incremental, a decidir na execução) — mesmo princípio já usado em
  `shared/proto/edge-openapi.yaml` para Edge↔Nuvem, estendido para FE↔BE.
- Início incremental: cobrir primeiro os domínios com achados P0/P1 no mapa (cameras, alerts,
  counting, branding) — não todos os ~250 endpoints de uma vez.

### 3. Geração de tipos TS a partir do OpenAPI

- Tipos em `apps/frontend/src/types/` deixam de ser escritos à mão para os domínios cobertos por
  OpenAPI; geração via ferramenta a escolher na execução (ex.: `openapi-typescript`).
- Elimina a classe de bug "drift" que motivou esta task (front esperando campo que o backend
  renomeou sem avisar).

### 4. Contract test no CI

- Novo job (ou extensão do job `tsc`/`pytest` existente) que falha o CI se: (a) um service do
  frontend chama um path que não existe em nenhum blueprint; (b) o schema de response gerado diverge
  do tipo TS consumido. Non-blocking (warn-only) no início, para não travar o `develop` com o
  volume de divergências pré-existentes já catalogado no mapa; vira gate bloqueante depois que o
  backlog (item 5) for zerado para os domínios cobertos.

### 5. Placeholders e duplicatas — backlog, não big-bang

- Corrigir caso a caso, priorizado pela tabela de divergências do mapa (P0 primeiro), cada um como
  sua própria task/PR pequeno — não uma reforma única. Achados de **segurança** (cross-tenant,
  endpoint perigoso sem role-gate) encontrados no levantamento já foram sinalizados separadamente
  para triagem humana urgente e não aguardam este ADR para ação.

## Alternativas consideradas

- **Big-bang**: mover tudo pra `/api/v1` e gerar OpenAPI completo numa única task. Rejeitada — alto
  risco de regressão num sistema com ~250 endpoints e cobertura de teste desigual; contraria o
  princípio do projeto de mudança incremental com CI verde a cada passo.
- **Não fazer nada / manter status quo**: rejeitada implicitamente pela motivação da própria
  task-069 (bug de drift já aconteceu em produção) — mas a decisão final de investir neste esforço
  ainda é do humano revisor.
- **OpenAPI first, sem convergir família de rota**: gerar contrato documentando o estado atual
  (com as duas famílias) sem convergir para `/api/v1`. Mais barato, mas perpetua a inconsistência;
  listada aqui como opção intermediária caso o revisor prefira reduzir escopo.

## Consequências

- Nenhuma agora — este ADR não é executado. Ao ser aceito, item 1-4 vira trabalho de Fase 2
  (task-069 Fase 2 ou tasks derivadas), sempre com PR pequeno + CI verde por incremento, nunca
  como mudança única de grande superfície.

## Pendências para o revisor humano

1. Aprovar, rejeitar ou pedir alternativa (ver seção acima).
2. Escolher ferramenta de geração de OpenAPI/tipos (não decidido aqui — decisão técnica de baixo
   risco, mas fica explícita como pendência).
3. Priorizar quais domínios entram primeiro no contract-test (sugestão: os com achados P0 do mapa).
4. Confirmar que os achados de segurança reportados em `docs/API_CONTRACT_MAP.md` (Resumo
   Executivo) serão tratados como tasks `risk:security` separadas, fora deste ADR.
