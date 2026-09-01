# ADR-0070 — Nome de modelo é rótulo de exibição, não versão semântica

- **Status:** Aceita
- **Data:** 2026-08-31
- **Decisor:** Vitor Emanuel
- **Contexto imediato:** `infra/migrations/129_trained_models_display_name.sql`
  (F5-LEVE, 30/08) e `apps/frontend/src/services/modelDisplay.ts` documentam,
  os dois, que `display_name` é "atribuído manualmente... nunca inferido...
  não existe V<n> calculado". `services/api/app/infrastructure/queue/tasks/training.py`
  faz exatamente o oposto: calcula `display_name = "Logikos V<n> · DD/MM"` na
  criação de todo modelo, sempre que `tenant_id` é resolvível. Achado
  verificando o contrato A1 (rodada 2 de correção UX) contra o código real.

---

## Decisão

**Mantém o cálculo.** A política que a migration 129 e o `modelDisplay.ts`
descrevem — "nunca inferido, nunca V<n> calculado" — está errada em relação
ao código real e não volta a valer: a alternativa é o cliente ver o `name`
interno cru (`"RF-DETR - Job 0307e2b1"`) ou nenhum nome, e ambas violam a
política mais antiga e mais forte, a de que **stack interno nunca chega ao
tenant** (mesma migration 129, mesma `modelDisplay.ts`).

O que muda é o **estatuto** do nome calculado:

1. **É rótulo de exibição, não versão semântica.** "Logikos V3" não afirma
   que o modelo 3 é melhor que o modelo 2 — afirma só que foi treinado
   depois. Um re-treino pode piorar métricas (dataset mal curado, classe
   nova ainda com poucos exemplos). O formato `V<n>` sugere ordem de
   qualidade onde só há ordem cronológica, e essa sugestão falsa é
   exatamente o motivo do refinamento pedido abaixo.
2. **Nome atribuído por humano sempre vence o calculado.** Quando existir
   uma rota que grave `display_name` por escolha de alguém (não existe
   ainda — ver "O que fica pendente"), essa rota nunca pode ser
   sobrescrita por uma recomputação automática subsequente.
3. **Os dois têm que ser visualmente distinguíveis na tela.** O cliente
   precisa saber, olhando, se aquele nome foi escolhido por uma pessoa ou
   gerado pela máquina — a mesma razão pela qual a ADR-0068 separa fatos
   que parecem a mesma coisa mas não são.
4. **UUID, `job_id`, framework (YOLOX/RF-DETR/YOLO26) e o `name` interno
   nunca aparecem para o tenant.** Reafirma a política já vigente (migration
   129, `modelDisplay.ts`) — este ADR não move essa fronteira.

### Refinamento registrado para depois do embarque

Trocar o formato `Logikos V<n> · DD/MM` por um rótulo descritivo e honesto,
que não sugira ranking: **`Logikos · DD/MM · N imagens`** — a data e o
tamanho do dataset são fatos verificáveis; "V3" é uma alegação de mérito que
o sistema não pode sustentar. Fora do escopo desta rodada (exige plumbing de
`dataset_versions` até o ponto do dispatch — ver `_build_display_name` em
`training.py:169-181`, que já registra essa lacuna: "não há dado de delta de
dataset disponível" ali).

---

## Os números que forçaram

- Grep completo do backend (`display_name`) confirma: o único escritor da
  coluna é `dispatch_training` em
  `services/api/app/infrastructure/queue/tasks/training.py:302-323`. **Não
  existe hoje nenhuma rota PATCH/rename que grave `display_name` por
  atribuição humana** — nem em `training/`, `models/`, `dashboard_edge/`.
- Medição real, DB DEV (RVB, tenant `63c219d8-fbef-4f3c-a7c9-058c742482e2`),
  31/08/2026: **11 `trained_models`** registrados. O mais recente
  (`8b3bd146…`, 25/08/2026 07:54) usa `dataset_version_id c36f6096…`, com
  **`frame_count = 2362`** imagens (1702 train / 300 val / 360 test). É o
  número real que sustenta o exemplo do refinamento: `Logikos · 25/08 ·
  2.362 imagens`, não um número inventado.
- Nenhum dos 11 `trained_models` do RVB tem `display_name` preenchido — não
  é bug: todos foram criados entre 21/08 e 25/08, e a coluna só passou a
  existir com a migration 129 (30/08). O cálculo em `training.py` roda para
  todo modelo criado **depois** de 30/08; os 11 existentes ficam com
  `display_name IS NULL`, o que o front já trata (`nomeParaCliente` cai para
  `"Logikos"`).

---

## Consequências

### Exigido
- `services/api/app/infrastructure/queue/tasks/training.py` continua
  calculando `display_name` na criação — nenhuma mudança de comportamento
  neste ADR.
- `apps/frontend/src/services/modelDisplay.ts` passa a documentar a política
  certa (corrigido nesta rodada, citando este ADR) — o comentário que dizia
  "não existe V<n> calculado" mentia sobre o próprio código que ele
  documenta.
- Qualquer rota futura que permita renomear um modelo (D3/refinamento) tem
  que gravar de um jeito que sobreviva a uma recomputação automática
  posterior — "humano sempre vence" vale a partir do dia em que essa rota
  existir, não é opcional.
- Toda superfície nova que mostrar nome de modelo ao tenant continua
  passando por `nomeParaCliente`/`nomeInternoOuCliente` (regra já vigente,
  ADR não move).

### Proibido
- ⛔ Reverter para "não existe V<n> calculado" apagando o cálculo em
  `training.py` — isso troca uma sugestão falsa de ranking por um vazamento
  pior (`name` interno cru ou nome vazio).
- ⛔ Editar `infra/migrations/129_trained_models_display_name.sql` para
  corrigir o comentário — é migration aplicada, forward-only (regra da
  casa). Este ADR é que a supersede nesse ponto específico; a migration
  permanece no disco como está.
- ⛔ Tratar o rótulo calculado como fonte de verdade sobre qualidade do
  modelo — nenhuma tela, alerta ou comparação pode ler "V3 > V2" como "V3 é
  melhor". A única leitura válida de `V<n>` hoje é ordem de criação.

---

## O que fica pendente (pedido ao backend, não decidido aqui)

**Como distinguir, no schema, "veio do cálculo" de "veio de atribuição
humana".** Medido antes de decidir: hoje não há como, porque só existe UM
escritor (o cálculo automático) — não existe ainda a rota que um humano
usaria para atribuir manualmente. Sem um segundo escritor real, qualquer
coluna de proveniência (`display_name_source enum('auto','human')`,
`display_name_set_by`, timestamp) seria especulativa — exatamente o tipo de
schema decidido sob pressão que a casa já lamentou uma vez (ADR-0069, mesmo
padrão de erro). **Não foi inventada aqui.**

Fica registrado como pré-requisito de quem construir a rota de renomeação
manual: essa rota PRECISA nascer junto com a coluna de proveniência (ou
equivalente), porque é o mesmo commit que cria o segundo escritor e torna a
regra "humano sempre vence" e "visualmente distinguível" (pontos 2 e 3 da
Decisão) implementáveis de fato. Até lá, os dois pontos são política escrita
sem mecanismo — este ADR não finge que o mecanismo já existe.

## O que isto NÃO decide

- O texto exato do rótulo refinado (`Logikos · DD/MM · N imagens` é exemplo,
  não especificação fechada) — fica para quem implementar o refinamento.
- O mecanismo de proveniência auto×humano (coluna, enum, timestamp) — ver
  seção acima.
- Se/quando a rota de renomeação manual será construída — não estava no
  escopo desta rodada, só a política para quando existir.

---

## Alternativas consideradas

- **Apagar o cálculo, deixar `display_name` sempre NULL até atribuição
  manual** (a política que a migration 129 e `modelDisplay.ts` descreviam
  literalmente). Rejeitada: front já cai para `"Logikos"` sem sobrenome
  nenhum quando NULL — pior que "Logikos V3", que ao menos distingue
  modelos entre si na tela (dropdown, histórico). Trocaria uma sugestão
  falsa de ranking por nenhuma informação.
- **Inventar a coluna de proveniência agora, sem a rota de renomeação.**
  Rejeitada pelo mesmo motivo da ADR-0069: schema decidido sob pressão, sem
  o segundo escritor real para validar o desenho contra.
- **Renomear já para o rótulo descritivo (`· N imagens`) nesta rodada.**
  Rejeitada: exige mudança de código (buscar `frame_count` do
  `dataset_version` no ponto do dispatch) fora do que foi pedido — esta
  rodada é a decisão escrita, o refinamento é rodada separada.

---

## Relacionadas

- **ADR-0068** — dois fatos que parecem a mesma coisa precisam de definição
  escrita e separação visual; mesmo molde aplicado aqui a "nome calculado" ×
  "nome humano".
- **ADR-0069** — mesmo padrão de erro (schema novo decidido sob pressão,
  sem o segundo caso real para validar) — motivo de não inventar a coluna
  de proveniência agora.
- `infra/migrations/129_trained_models_display_name.sql` — parcialmente
  superseded por este ADR (o comentário "nunca... não existe V<n>
  calculado"); a coluna e o resto da migration continuam válidos.
- `services/api/app/infrastructure/queue/tasks/training.py:169-181,302-323`
  — `_build_display_name`/`dispatch_training`, o único escritor hoje.
- `apps/frontend/src/services/modelDisplay.ts` — corrigido nesta rodada
  para citar este ADR em vez de descrever a política antiga.
