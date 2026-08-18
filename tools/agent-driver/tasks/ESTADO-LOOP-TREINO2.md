# ESTADO — Loop TREINO 2

> Arquivo de estado do loop. **Primeiro ato de toda sessão: ler este arquivo.**
> Ele SOBRESCREVE a tabela de estado do prompt. Atualizar a cada marco: commit + push.

**Última atualização:** 2026-08-18 · sessão 1 · marco em curso: **M2** · aguardando job fechar para M3

## PROVADO

- Causa das 4 falhas de época 0: o dispatch **não usa o `dataset.zip`** — reconstrói o zip a partir
  dos **objetos soltos** sob `{coco_r2_key}/train|val|test/` (`training.py:390-411`) e **sobrescreve**
  o zip. O `v5-relabel` só tinha o zip → zip de 22 bytes → pod sem classes.
- Conserto aplicado: **398 objetos soltos** subidos (train 211 / val 7 / test 180 — idêntico ao
  `v3-treino1`). Reprodução local do caminho do pod **passou** a US$ 0.
- COCO do `v5-relabel`: placeholder `id:0 / supercategory:"none"` restaurado (formato do `v3` que
  treinou) · **11 classes efetivas** (`Capacete` tem 0 no train, dropada pelo guard) ·
  test **179 img · mascara=54** · train **210 img · mascara=57**.
- DEV serve `26912945`, provado por `/livez`. Auto-deploy por git. ⛔ nunca `railway up`.
- Payload estrito em produção (`epochs` → 400). Não-rebaixamento de `error_message` funcionando
  (causa de 136 chars sobreviveu ao clobber).
- Sensor de re-export: **zero disparos** — porque nunca houve build fantasma; era o próprio dispatch.

## RODANDO

Job `f0cc48eb` (pod `hrnoq4y83r2oj5`) — reportou `Module onnx is not installed!` **porque o worker
nunca recebeu o conserto**. Aguardando fechar.

## PRÓXIMO PASSO

🔴 **CAUSA RAIZ ENCONTRADA — o `celery-worker` do DEV está parado em 2026-08-13.**

`dispatch_training` é task **Celery**: roda no serviço **`celery-worker`**, NÃO na `API-V3`. É ele que
lê `training/vast/remote_train.py` do próprio container (`repo_files.find_repo_file`) e manda o código
ao pod. O último deploy do worker é de **13/08, sem `commitHash`**.

**Logo: NENHUM conserto chegou ao pod** — nem o `onnx` (#401), nem D1/D2/D3 (#406), nem o pré-flight
da fonte (#398). Eu vinha conferindo `/livez` da **API**: o sensor certo, no **serviço errado**.

Isto explica a série inteira de falhas e reclassifica a parada #4: **não é a mesma causa falhando 2×
após conserto — é o conserto nunca ter sido implantado.**

**Ordem da retomada:**
1. **Deployar o `celery-worker`** a partir da develop (auto-deploy por git; ⛔ nunca `railway up`).
   ⚠️ Ele não tem `/livez` — a verificação precisa ser outra: comparar `commitHash` do deployment
   pela API do Railway, ou criar um sinal equivalente.
2. Confirmar que o worker serve o SHA da develop.
3. Re-disparar. Com D1+D2 no worker, uma falha agora traz log do pod e não é apagada por retry.

⚠️ **Lição para o ESTADO:** conferir o SHA de **todos os serviços que participam do caminho**, não só
do que responde HTTP. A API é a porta; o worker é quem faz.

## PODS E CUSTOS ACUMULADOS

| Pod | Job | Resultado |
|---|---|---|
| `anitowclpklzk0` | 5754bc17 | falhou ép. 0 — morto (404) |
| `ro6fdmavjo83bz`, `z6x0gqd10g8us6` | 40c38d79 | falhou ép. 0 — mortos (404) |
| `jeml62k3k3zsad` | 16dc8b89 | falhou ép. 0 — morto (404) |
| `qqcfyalybiiw5k`, `h8lsxxh182gnm3` | a451015a | falhou ép. 0 — mortos (404) |
| `1juqegc78rltxm` | f183719a (retry) | falhou no export — **morto (404)** |
| `hrnoq4y83r2oj5` | f0cc48eb | 🔴 **RODANDO** — 1º com D1+D2+D3 |
| `c9j7jkcatafs2g` | 6d00cc0c | **falhou** (chegou a ep 29, depois retry em ep 0) — morto (404) |
| `3wqbuxbm2xz8cw` | f183719a | ✅ **TREINOU** — morreu só no export ONNX — **morto (404)** | **running ep 12** — passou da época 0, 1ª vez |

**Custo acumulado: INDETERMINADO** — `actual_usd` só passou a ser gravado depois desses pods, e todos
morreram antes. ⛔ Não estimar. Teto da missão: US$ 10.

## DECISÕES TOMADAS

- Conta `claude-ops` (tenant `rvb`, admin) criada para destravar o DEV; senha em `OPS_ADMIN_*`.
- `dataset_version` em `ready` é imutável (guard + sensor) — mas ver M4: **objetos soltos são a
  FONTE, o zip é cache derivado**; a imutabilidade precisa mirar a fonte.
- Guard de suporte-zero: classe sem instância no train sai do mapa (`Capacete`).
- GATE: falha de infra se reproduz a US$ 0 antes de qualquer re-disparo. Custo de não ter tido: 4 pods.
- **M1 (PR #398):** pré-flight passa a validar a FONTE (objetos soltos por split), não o zip — que é
  cache derivado, reconstruído e sobrescrito pelo dispatch a cada disparo. E `download()` do runner
  confere status/magic PK/entradas, com erro que diz O QUE veio (um 404 do R2 responde XML).
- **M5 iniciado:** Orin acessível por SSH, **56 GB livres de 116 GB (50%)** — reserva intacta.
  Retenção do DVR NÃO medida: exige requisição ao gravador e o anti-lockout pede execução dedicada,
  não no fim de uma sessão. O minerador assume `days=8` por default (`replay_miner.py:662`) — isso é
  suposição do código, **não medição**.
- **PR #401:** `onnx` e `onnxruntime` explícitos no runner. `pip_install("rfdetr", "rfdetr[onnx]", ...)`
  fazia o pip considerar o requisito satisfeito pelo primeiro e PULAR o extra — o treino rodava
  inteiro e morria no export, depois de pagar a GPU toda.
- ⚠️ `current_epoch` reporta passo dentro da época, não época (subiu a 49, voltou a 32, depois 13).
- **D1 (PR #406):** `max_retries=0` no dispatch GPU, permanente. Retry automático apaga a evidência da
  tentativa informativa, dobra o custo e repete a mesma falha. Re-tentar é decisão do loop.
- **D2 (PR #406):** log do pod capturado ANTES do `terminate_pod` → R2 `jobs/{id}/pod.log` + últimas
  50 linhas no `error_message`. Antes, toda falha de pod era cega POR CONSTRUÇÃO.
- **D3 (PR #406):** escritores de `training_jobs.status='failed'` enumerados — watchdog
  (`runpod_runner._watch`), reconciler (`gpu_reconciler._mark_job_failed`) e dispatch. Os três gravam
  causa; testes fixam.
- 💰 **Billing do RunPod: API responde HTTP 400** em `/v1/billing`, `/v1/user`, `/v1/account` — a conta
  não expõe gasto por API. **Custo total segue INDETERMINADO**; o D2 impede que se repita.
- 🔴 **Corrida de deploy CONFIRMADA por metadado:** `railway up` de outra sessão sobrescreveu dois
  deploys por git seguidos (#401 e #402). O `/livez` com `commit:"unknown"` é o detector — funcionou.
  Antes de qualquer disparo: conferir que `/livez` == SHA da develop.
