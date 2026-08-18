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

Nada. Job `f183719a` fechou `failed`; pods `3wqbuxbm2xz8cw` e `1juqegc78rltxm` **mortos (404)**.

## PRÓXIMO PASSO

🔴 **BLOQUEIO: o conserto do onnx NÃO está no ar.**

O deploy vigente do DEV (`6531d9f7`, 04:31) **não tem `commitHash`** — é um `railway up` — e
sobrescreveu o deploy por git do `#402` (que já continha o `#401`, o conserto do onnx).
`/livez` responde `commit: "unknown"`, que é exatamente o sinal que ele foi criado para dar.

**Não foi esta sessão** (último `railway up` daqui: 00:22). É outra sessão no mesmo serviço — a corrida
já registrada em `dev-api-singleton-race`.

**Ordem da retomada:**
1. Conferir `/livez` — se `unknown` ou SHA != develop, **forçar redeploy por git** (`railway redeploy`
   do serviço, ou push vazio na develop). ⛔ **NÃO usar `railway up`** — seria repetir a causa.
2. Só com `/livez` == SHA da develop: **re-disparar** `total_epochs:12`, `base_model=base`, `v5-relabel`.
3. **M3 — veredito** contra D-163.

## PODS E CUSTOS ACUMULADOS

| Pod | Job | Resultado |
|---|---|---|
| `anitowclpklzk0` | 5754bc17 | falhou ép. 0 — morto (404) |
| `ro6fdmavjo83bz`, `z6x0gqd10g8us6` | 40c38d79 | falhou ép. 0 — mortos (404) |
| `jeml62k3k3zsad` | 16dc8b89 | falhou ép. 0 — morto (404) |
| `qqcfyalybiiw5k`, `h8lsxxh182gnm3` | a451015a | falhou ép. 0 — mortos (404) |
| `1juqegc78rltxm` | f183719a (retry) | falhou no export — **morto (404)** |
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
