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

Nada. Nenhum pod vivo.

## PRÓXIMO PASSO

🔴 **PARADA #4 DO PROTOCOLO — devolvido ao Vitor.**

Job `6d00cc0c` (1º disparo com o onnx no ar) **falhou**. Sinal disponível:

| | |
|---|---|
| `error_message` | `"Job runpod failed: job=..."` — **genérico, 59 chars** |
| `metrics` | `{}` |
| `current_epoch` no fim | **0** (mas chegou a **29** antes → houve retry do Celery) |
| Pod `c9j7jkcatafs2g` | **morto (404)** — logs perdidos |

⛔ **Não consigo provar a causa.** Pode ser o onnx de novo (2ª vez após conserto) ou outra coisa.

### 🔴 A lacuna que isto expõe na instrumentação

O não-rebaixamento de `error_message` só preserva mensagem específica **se alguma tiver sido escrita**.
Nesta falha **nenhuma foi** — logo o caminho que falhou **não passa pelo callback do pod**. A
instrumentação cobre o callback e o `_watch`; falta o caminho que produziu esta falha.

**Antes de qualquer 3ª tentativa:**
1. Descobrir de onde sai um `failed` SEM nenhuma escrita de causa (provavelmente o retry do Celery
   falhando antes de o pod reportar — `dispatch_training` re-executa e o 2º pod morre cedo).
2. Capturar log do pod ANTES de ele morrer (hoje o `terminate_pod` no `finally` apaga a evidência).
   Sem isso, toda falha de pod é cega por construção.
3. Considerar `max_retries=0` no `dispatch_training` durante a investigação: o retry automático
   dobra o custo e **sobrescreve o estado da 1ª tentativa**, que era a informativa.

## PODS E CUSTOS ACUMULADOS

| Pod | Job | Resultado |
|---|---|---|
| `anitowclpklzk0` | 5754bc17 | falhou ép. 0 — morto (404) |
| `ro6fdmavjo83bz`, `z6x0gqd10g8us6` | 40c38d79 | falhou ép. 0 — mortos (404) |
| `jeml62k3k3zsad` | 16dc8b89 | falhou ép. 0 — morto (404) |
| `qqcfyalybiiw5k`, `h8lsxxh182gnm3` | a451015a | falhou ép. 0 — mortos (404) |
| `1juqegc78rltxm` | f183719a (retry) | falhou no export — **morto (404)** |
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
- 🔴 **Corrida de deploy CONFIRMADA por metadado:** `railway up` de outra sessão sobrescreveu dois
  deploys por git seguidos (#401 e #402). O `/livez` com `commit:"unknown"` é o detector — funcionou.
  Antes de qualquer disparo: conferir que `/livez` == SHA da develop.
