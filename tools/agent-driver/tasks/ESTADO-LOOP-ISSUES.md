# ESTADO — LOOP de ISSUES (faixa paralela à Missão DADO)

**Sessão 1:** 2026-08-18 · **Worktree:** `~/Logikos-mutirao/wt-issues` (clone rápido — ⛔ não o
checkout em `Documents`, que sofre eviction do iCloud) · **Branches:** `fix/issues-loop-*`,
`fix/NNN-*` de `origin/develop`.

## Faixa — o que esta sessão NÃO toca

⛔ `services/edge-sync-agent` (minerador) · ⛔ o box/Orin · ⛔ tela de anotação (`CropClassifier*`,
fila, matriz) · ⛔ `ESTADO-LOOP-DADO.md` / `ESTADO-LOOP-TREINO2.md` · ⛔ disparar treino/pod ·
⛔ variáveis do Railway · ⛔ `railway up`.

## Regra 2 — pod em voo antes de TODO merge

⚠️ **Esta sessão NÃO tem credencial do banco DEV.** O `.env` do checkout em `Documents` aponta para
`localhost:5432` (banco vazio) — checar `training_jobs` por ali **mente**, devolve zero porque a
tabela está vazia, não porque não há pod.

**Como foi feito:** perguntei à sessão par (`camera-1-rvb-annotation-loop-7ecfe8-c2`, a da Missão
DADO) por `SendMessage` antes de mergear. Registro da resposta abaixo, por merge.

| merge | checagem | resposta |
|---|---|---|
| (pendente) | pergunta enviada à sessão DADO em 18/08 | ⏳ aguardando |

## PRs desta rodada

| PR | issue | o que faz | estado |
|---|---|---|---|
| #450 | #447 | registro de decisões: um arquivo por decisão + índice gerado + gate (regra 7) | aberta, CI verde |
| #452 | #417 | piso de medição: avaliação sem predição vira `reject` | aberta, empilhada em #450 |
| (esta) | #428 | Excluir câmera → **Arquivar**; `delete` sai da camada de serviço do front | em curso |

## Issues abertas por esta sessão

- **#447** registro de decisões colide entre sessões *(não existia issue; criada antes do PR)*
- **#451** pós-processamento RF-DETR do produto diverge do harness calibrado — ordem das saídas,
  `softmax` × `sigmoid`, `topk`. **Desdobramento do #417 deixado de fora de propósito:** exige o
  artefato `.onnx` para verificar e mexe na inferência ao vivo.

## Fila — o que falta na faixa

Por prioridade, confirmada no GitHub:

1. **#426** D-165 trava de split degenerado no export COCO
2. **#427** D-166 gate do bootstrap (só roda sem nenhum tenant)
3. **#419** `started_at` mente 8× · **#420** `current_epoch` reporta passo
4. **#445** FE hardcoda nome de classe — catálogo vem da API
5. Inventário "quem escreve o quê" *(⚠️ não existe issue — criar)*

## Fora da faixa — deixado para a Missão DADO / Vitor

- **#436** minerador conta falha de infra como janela vazia *(minerador)*
- **#442** consultar índice do DVR antes do replay *(minerador/edge)*
- **#446** aviso "crie a classe e volte depois" com a classe existindo *(tela de anotação)*
- **#429** contradição de 14/08 no TREINO 1 — o `ESTADO-LOOP-TREINO2` marca *"não perseguir"*

## Achados sem issue ainda

- `apps/frontend/src/components/cameras/CameraCard.tsx` **não é importado por nenhuma página** —
  só aparece como exemplo em `components/AGENTS.md`. Foi corrigido junto (arquivar em vez de
  excluir) em vez de removido, porque apagar componente é outra rodada.
- O `Índice rápido` do `REGISTRO_DE_DECISOES.md` listava 61 decisões para um corpo de 170 — índice
  à mão apodrece. Resolvido pelo índice gerado (#450).
