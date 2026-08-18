# ESTADO — Loop TREINO 2

> Arquivo de estado do loop. **Primeiro ato de toda sessão: ler este arquivo.**
> Ele SOBRESCREVE a tabela de estado do prompt. Atualizar a cada marco: commit + push.

**Última atualização:** 2026-08-18 · sessão 1 · marco em curso: **M2 → M3** · sessão 1 esgotada

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

🔴 **TREINO 2 — job `f183719a`, pod `3wqbuxbm2xz8cw`. AINDA RODANDO ao fim da sessão 1.**
Estado na saída: `running ep 12`.

- **PASSOU DA ÉPOCA 0** — 1ª vez em 5 tentativas. A causa provada (fonte do dataset) era mesmo essa.
- ⚠️ `current_epoch` NÃO é época: subiu a 49 e voltou a 32. Reporta passo dentro da época. Não é bloqueio.
- ⚠️ **O pod já reportou `Module onnx is not installed!`** pelo callback, com o job ainda `running`.
  O treino avança, mas o export ONNX provavelmente falha no fim. **Se o job fechar `failed` com essa
  mensagem: é dependência faltando na imagem do runner, não dataset.** Conserto = instalar `onnx` no
  `remote_train.py` (pip_install já existe lá). GATE: reproduzir a US$ 0 antes de re-disparar não se
  aplica — a mensagem já é a prova.

**Retomada:** ler o status do job `f183719a`. Se `completed` → M3 (veredito). Se `failed` por onnx →
conserto de 1 linha + re-disparo (é a 1ª falha dessa causa, não a 2ª).

## PRÓXIMO PASSO

**M3 — o veredito**, assim que o job fechar:
precisão de `mascara` vs baseline **0,4375** · n de predições · matriz de confusão ·
**11 classes efetivas** declaradas · `actual_usd` · morte do pod por NOVA consulta.
Limiares (D-163, não reescrever): **>0,61 sinal real** · 0,50–0,61 ruído · <0,50 sem suporte.
Assimetria: gabarito endureceu — subir = forte, cair = ambíguo.

## PODS E CUSTOS ACUMULADOS

| Pod | Job | Resultado |
|---|---|---|
| `anitowclpklzk0` | 5754bc17 | falhou ép. 0 — morto (404) |
| `ro6fdmavjo83bz`, `z6x0gqd10g8us6` | 40c38d79 | falhou ép. 0 — mortos (404) |
| `jeml62k3k3zsad` | 16dc8b89 | falhou ép. 0 — morto (404) |
| `qqcfyalybiiw5k`, `h8lsxxh182gnm3` | a451015a | falhou ép. 0 — mortos (404) |
| `3wqbuxbm2xz8cw` | f183719a | 🔴 **running ep 12** — passou da época 0, 1ª vez |

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
