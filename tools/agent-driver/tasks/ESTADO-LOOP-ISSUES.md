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

## ✅ Regra 2 — RESOLVIDA ESTRUTURALMENTE (não pergunte mais)

```bash
curl -s https://api-v3-desenvolvimento.up.railway.app/livez | jq .running_jobs
# 0 → pode mergear · null → BLOQUEIA (null nunca vira 0)
```

`/livez` ganhou `running_jobs` (#468, D-182). Lido do cache do refresher — o handler continua
**sem tocar o banco**, porque é o probe que o Railway usa para reiniciar processo travado.
⚠️ `null` = não sei (sem ciclo · snapshot velho · banco fora). A regra é `== 0`, então `null`
bloqueia. Confirmado no ar: `{"commit":"39a4ead…","running_jobs":0}`.

### Histórico do impasse que motivou isso

⚠️ **Esta sessão NÃO tem credencial do banco DEV.** O `.env` do checkout em `Documents` aponta para
`localhost:5432` — banco **vazio**. Consultar `training_jobs` por ali **mente**: devolve zero porque a
tabela está vazia, não porque não há pod. Foi tentado e descartado.

**Método usado:** perguntar à sessão par por `SendMessage`.

| # | quando | a quem | resposta |
|---|---|---|---|
| 1 | 18/08, antes do 1º merge | `camera-1-rvb-annotation-loop-7ecfe8-c2` | ⏳ sem resposta |
| 2 | 18/08, repetida | `camera-1-rvb-annotation-loop-7ecfe8-c2` | ⏳ sem resposta |
| 3 | 18/08 | `epi-cath-v2-09` (pedindo só a contagem, ⛔ nunca a URL) | ⏳ **sem resposta até o fim da sessão** |

🛑 Na primeira volta, **nenhum merge foi feito** — 3 perguntas sem resposta. ✅ Destravado por
**confirmação humana do Vitor** (console do RunPod: zero pods; a DADO havia terminado a prova de
retomabilidade com todos os pods mortos). As 9 PRs mergearam em sequência.

⚠️ **É esse impasse que o `running_jobs` remove.** Não repita a pergunta: use o curl.

⛔ **Não** volte a consultar banco à mão para isso: foi assim que uma sessão leu "zero pods"
porque a tabela estava vazia, não porque não havia pod.

## PRs desta rodada — ✅ TODAS MERGEADAS na `develop`

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
| 7 | #461 | #460 | inventário **quem escreve o quê** (⛔ só leitura) |
| 8 | #464 | #459 | dispatch para de escrever por cima do que o pod reportou |
| 9 | #468 | #467 | `/livez` responde "há pod em voo?" — `running_jobs` |

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

1. 🔴 **Regra 2 + merge das 8 PRs na ordem da tabela** (é a única coisa que falta nelas)
2. **#425** — `railway up` de sessão paralela sobrescreve deploy por git (§5 do inventário)
4. **#424** — worker Railway sem watch patterns
5. **#434** — `nixpacks`/`railway_start` apontam para `landing-page/`, diretório que não existe
6. **#422** — arquivos de credencial guardam `NOME=valor` e o consumo cola o nome no bearer
7. **#427** — só depois de medir com o `split_warnings` do #454

## Notas operacionais desta rodada (para não repetir)

- ⚠️ **CI só roda em PR com base `develop`/`staging`/`main`.** PR empilhada com base em branch de
  feature fica **sem check nenhum** — e "verde" vazio parece verde. Além disso, **trocar a base NÃO
  redispara** o workflow (o `pull_request` só escuta opened/synchronize/reopened): foi preciso
  `gh pr close` + `gh pr reopen` para disparar.
- ⚠️ **`security-scan.yml` está VERMELHO na `develop`** — é a issue #421 (astro 4.16.19, 3 high).
  ⛔ Não é regressão desta rodada, e ⛔ não entra nos 10 checks do rollup de PR. Como é
  `risk:security`, **para a fila para revisão humana** — não foi tocada.
- A pilha foi **rebaseada** depois de dois achados de auto-revisão (teto de id COCO e `int(total)`
  defensivo). Se rebasear de novo, force-push com `--force-with-lease`, de baixo para cima.
- ⛔ **Workflow de subagentes indisponível** nesta sessão: 14 agentes, 14 erros `529 Overloaded`, em
  duas tentativas. O diagnóstico das issues restantes foi feito direto.

## Auto-revisão adversarial — o que ela achou nas próprias PRs

| achado | onde | corrigido em |
|---|---|---|
| id de categoria COCO absurdo alocaria lista de milhões | `_class_names_from_coco` | commit no #452 |
| `int(total_epochs)` seco derrubaria o callback do pod inteiro se o campo viesse ilegível | `_epoca_confiavel` | commit no #458 |

⚠️ Um guard de sanidade que quebra o caminho feliz é pior que guard nenhum — foi a lição das duas.

## Estado verificado ao fim da sessão

| | |
|---|---|
| `develop` | `39a4ead` |
| `/livez` do DEV | `39a4ead` · `running_jobs: 0` · `status: alive` |
| `/readyz` do DEV | 200 |
| decisões no registro novo | 176 arquivos (`docs/decisions/D-*.md`) |
| suíte unitária | 3814+ passed |

⚠️ **`security-scan.yml` continua VERMELHO na `develop`** — issue #421 (astro 4.16.19, 3 high). ⛔ Não
é regressão desta rodada e ⛔ não entra nos 10 checks do rollup de PR. É `risk:security` → fila humana,
já com o Vitor.

⚠️ **#456 mergeou com o job de frontend ainda na fila** do runner (os outros 9 checks verdes; o mesmo
código de frontend passou em 7 PRs irmãs e no merge da develop depois). Registrado por honestidade,
⛔ não por suspeita.
