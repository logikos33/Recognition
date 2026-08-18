# ESTADO — LOOP de ISSUES (faixa paralela à Missão DADO)

**Sessão 1:** 2026-08-18 · **Worktree:** `~/Logikos-mutirao/wt-issues` (clone rápido — ⛔ **não** o
checkout em `Documents`, que sofre eviction do iCloud e trava `git log --all`) · **Branches:**
`fix/*` de `origin/develop`.

## Faixa — o que esta sessão NÃO toca

⛔ `services/edge-sync-agent` (minerador) · ⛔ o box/Orin · ⛔ tela de anotação (`CropClassifier*`,
`cropClassifierLogic.ts`, fila, matriz) · ⛔ `ESTADO-LOOP-DADO.md` / `ESTADO-LOOP-TREINO2.md` ·
⛔ disparar treino/pod · ⛔ variáveis do Railway · ⛔ `railway up`.

**Provado por diff:** nenhum arquivo dessas áreas foi tocado. O único acerto de `grep` na faixa foi
`docs/decisions/D-116-recon-…-minerador-dvr-….md` — arquivo de **documentação** copiado pelo script de
migração do registro, ⛔ zero código de minerador.

## 🔴 Regra 2 — pod em voo antes de TODO merge

⚠️ **Esta sessão NÃO tem credencial do banco DEV.** O `.env` do checkout em `Documents` aponta para
`localhost:5432` — banco **vazio**. Consultar `training_jobs` por ali **mente**: devolve zero porque a
tabela está vazia, não porque não há pod. Foi tentado e descartado.

**Método usado:** perguntar à sessão par por `SendMessage`.

| # | quando | a quem | resposta |
|---|---|---|---|
| 1 | 18/08, antes do 1º merge | `camera-1-rvb-annotation-loop-7ecfe8-c2` | ⏳ **sem resposta até o fim da sessão** |

🛑 **NENHUM MERGE FOI FEITO.** As 7 PRs ficam abertas e verdes. Merge sem a resposta violaria a
regra 2 — deploy do worker mata o vigia de pod em voo, e já houve pod órfão de vigia.

**Próxima sessão:** repetir a pergunta antes de mergear. Se a sessão par não existir mais, o caminho
honesto é obter a `DATABASE_PUBLIC_URL` do DEV e checar
`select status, count(*) from public.training_jobs group by 1` — ⛔ nunca imprimir a URL.

## PRs desta rodada — todas com base `develop`, ⛔ nenhuma mergeada

⚠️ **São empilhadas**, nesta ordem (cada uma contém as anteriores até mergearem). O acoplamento é só
`docs/decisions/INDICE.md`, que é gerado.

| ordem | PR | issue | o que faz |
|---|---|---|---|
| 1 | #450 | #447 | registro de decisões: **um arquivo por decisão** + índice gerado + gate (regra 7) |
| 2 | #452 | #417 | **piso de medição**: avaliação sem predição vira `reject` |
| 3 | #453 | #428 | Excluir câmera → **Arquivar**; `delete()` sai da camada de serviço do front |
| 4 | #454 | #426 | guard de **split degenerado** no export COCO (executa D-165) |
| 5 | #456 | #455 | bootstrap de admin **só em instalação virgem** (executa D-166) |
| 6 | #458 | #419, #420 | `started_at` e `current_epoch` passam a dizer a verdade |
| 7 | (esta) | #460 | inventário **quem escreve o quê** (⛔ só leitura) |

⚠️ **CI só roda em PR com base `develop`/`staging`/`main`** (`.github/workflows/ci.yml`). As PRs
nasceram empilhadas com base em branch de feature e **ficaram sem check nenhum** — foram reapontadas
para `develop`. Se empilhar de novo, reaponte, ou o "verde" é vazio.

## Issues abertas por esta sessão

| # | por quê |
|---|---|
| #447 | registro de decisões colide entre sessões — ⛔ não existia issue |
| #451 | **pós-processamento RF-DETR diverge do harness calibrado** (ordem das saídas, `softmax`×`sigmoid`, `topk`) — desdobramento do #417 deixado de fora **de propósito** |
| #455 | D-166 de verdade (a #427 leva "D-166" no título mas é outro assunto) |
| #459 | `training.py` sobrescreve `training_jobs.metrics` enquanto o repository funde |
| #460 | inventário quem escreve o quê |

## Fora da faixa — ⛔ não tocado

| # | por quê |
|---|---|
| #445 | FE hardcoda nome de classe → `cropClassifierLogic.ts` é **tela de anotação**. A própria issue termina com *"⛔ Não agora"* |
| #436 | minerador conta falha de infra como janela vazia |
| #442 | consultar índice do DVR antes do replay |
| #446 | aviso "crie a classe e volte depois" — tela de anotação |
| #429 | o `ESTADO-LOOP-TREINO2` marca *"não perseguir"* |

## ⚠️ O que NÃO deu para determinar

- **#427 (gate de mínimo de dados para treinar).** A issue exige *"números a definir a partir dos
  dados reais da RVB, ⛔ não de regra de bolso"* — e não há acesso ao banco DEV aqui. Inventar
  `min_por_classe = 50` seria a regra de bolso que a issue proíbe. **Comentei na issue** com o
  caminho para destravar: o `split_warnings` do #454 é de onde os números saem **medidos**.
- **#451 (pós-processamento RF-DETR).** Exige o `.onnx` do TREINO 2 e as 179 imagens do split `test`
  para verificar, e mexe na **inferência ao vivo**. Trocar `softmax` por `sigmoid` e inverter a ordem
  das saídas sem rodar o modelo é palpite confiante — o tipo de conserto que vira o próximo bug.
- **#459 (metrics sobrescrito).** Achado por **leitura de código**, ⛔ não reproduzido contra banco.

## Achados sem dono

- `apps/frontend/src/components/cameras/CameraCard.tsx` **não é importado por nenhuma página** — só
  aparece como exemplo em `components/AGENTS.md`. Foi corrigido junto (arquivar em vez de excluir) em
  vez de removido: apagar componente é outra rodada.
- O `Índice rápido` do `REGISTRO_DE_DECISOES.md` listava **61** decisões para um corpo de **170**.
  Índice mantido à mão apodrece — resolvido pelo gerado (#450).
- `railway_start.py` não tinha `if __name__ == '__main__'`: `import railway_start` **bootava um
  serviço**. Por isso nenhuma função do arquivo tinha teste. Corrigido em #456.

## Fila para a próxima sessão

1. 🔴 **Regra 2 + merge das 7 PRs na ordem da tabela** (é a única coisa que falta nelas)
2. **#459** — `metrics = %s` → `||`, com teste de sobrevivência de chave
3. **#425** — `railway up` de sessão paralela sobrescreve deploy por git (§5 do inventário)
4. **#424** — worker Railway sem watch patterns
5. **#434** — `nixpacks`/`railway_start` apontam para `landing-page/`, diretório que não existe
6. **#422** — arquivos de credencial guardam `NOME=valor` e o consumo cola o nome no bearer
7. **#427** — só depois de medir com o `split_warnings` do #454
