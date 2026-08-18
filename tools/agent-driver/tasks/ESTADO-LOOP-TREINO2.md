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

🔴 **TREINO 2 — job `14c65776`, pod `ioq1u89gz980it`.** 12 épocas, `base_model=base`, `v5-relabel`.
Worker em `a0f56f7d`+ (deploy POR GIT, `commitHash` presente). Treinando sem erro reportado.

## PRÓXIMO PASSO

**Ler o desfecho do job `14c65776`** → se `completed`, **M3: O VEREDITO** (D-163 intacto).

### 🔴 Três achados desta sessão que precisam de conserto

1. **`metrics.provenance` NÃO foi gravada** no job `14c65776`, mesmo com o worker em `a0f56f7d`
   (que inclui o #409). O `metrics` até regrediu de `{"stage":2.0}` para `{}` — algo o sobrescreve.
   ⚠️ Envolvi a escrita em `contextlib.suppress(Exception)`: se falhar, falha CALADA. **É o mesmo
   erro que venho consertando nos outros — cometi de novo no próprio conserto.** Trocar por log alto.
2. 🔴 **A captura de log do pod (D2) NÃO FUNCIONA:** `GET /v1/pods/{id}/logs` responde **HTTP 400**
   nesta conta RunPod. O `get_pod_logs` vai sempre devolver `""`. **O conserto de maior valor da
   parada #4 está inoperante** — precisa de outra via (GraphQL? webhook? o próprio runner subindo o
   log para R2 antes de sair?).
3. **Watch patterns: NÃO existem** no `worker-railway.toml` nem em nenhuma config — a hipótese de
   filtro de caminho está DESCARTADA. O worker não deployava porque `source` estava vazio; agora tem
   `repo: logikos33/Recognition · branch: develop` (confirmado por `get-service-config`).
   ✅ **RESOLVIDO: o Vitor conectou o repo manualmente no dashboard do Railway** (confirmado por ele).
   ⚠️ Consequência para o método: o `railway up` que fiz **não** foi o que destravou — foi ação humana.
   A ordem correta, daqui em diante, é: serviço sem `source` → **pedir/conectar o repo**, não empurrar
   `railway up`, que só mascara o problema com um deploy sem proveniência.

## LOG DO ÓRFÃO f0cc48eb — informativo, ⛔ NÃO é o veredito

O Vitor capturou o log do pod ao vivo (a API REST não entrega: `/v1/pods/{id}/logs` → HTTP 400).
Job de **50 épocas** (worker velho) — ⛔ segunda variável, não comparável com o baseline de 12.

| | |
|---|---|
| Treino | **saudável** — loss 7,29 → 4,91 entre ép. 10 e 43; `class_error` chega a 0,00 no train |
| `Test [0/2]` | são **2 batches = as 6 imagens do val**. AP@50 oscila **0,294–0,394** ali |
| AP@50:95 (val) | 0,149–0,168 · AR@500 0,225 |
| Fim do log | `Epoch: [43/50]` — onde eu terminei o pod |

🔴 **Leitura:** AP sobre 6 imagens é ruído, não medida. Serve só como sinal de que **o dataset
relabelado treina** — loss cai, o modelo aprende. ⛔ Não entra no D-163.

### 🔴 De onde o veredito REALMENTE vem (descoberto por este log)

O RF-DETR avalia só o `valid/` durante o treino. As métricas por classe no split **test (179 img)**
vêm de `evaluate_challenger_model` — task Celery que roda **depois**, e **só dispara se o job chegar a
`completed` e registrar o modelo**.

⚠️ **Consequência:** falhar no export ONNX = **nenhum veredito**, mesmo com treino perfeito. O export
não é detalhe de empacotamento; é pré-condição do número.

## PODS E CUSTOS ACUMULADOS

| Pod | Job | Resultado |
|---|---|---|
| `anitowclpklzk0` | 5754bc17 | falhou ép. 0 — morto (404) |
| `ro6fdmavjo83bz`, `z6x0gqd10g8us6` | 40c38d79 | falhou ép. 0 — mortos (404) |
| `jeml62k3k3zsad` | 16dc8b89 | falhou ép. 0 — morto (404) |
| `qqcfyalybiiw5k`, `h8lsxxh182gnm3` | a451015a | falhou ép. 0 — mortos (404) |
| `1juqegc78rltxm` | f183719a (retry) | falhou no export — **morto (404)** |
| `ioq1u89gz980it` | 14c65776 | 🔴 **RODANDO** — worker em a0f56f7d (git) |
| `hrnoq4y83r2oj5` | f0cc48eb | ⚠️ **ÓRFÃO** — worker trocado no meio do voo matou o watchdog. Achado VIVO a US$0,50/h com ~1h de uptime (~US$0,50), 50 épocas (dispatch do worker velho, ⛔ não é o experimento). **Terminado manualmente, morte provada (404)** |
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
- **PR #409:** proveniência do worker no próprio job — `metrics.provenance` com `worker_commit`
  (ou "unknown", denunciando `railway up`) e `runner_sha256` do runner enviado ao pod. É o `/livez`
  de quem não fala HTTP.
- 🔴 **REGRA:** proveniência cobre TODOS os serviços do caminho de execução, não só a porta de
  entrada. Caminho do disparo = API (`/livez`) **+ worker** (proveniência no job).
- 🔴 **Corrida de deploy CONFIRMADA por metadado:** `railway up` de outra sessão sobrescreveu dois
  deploys por git seguidos (#401 e #402). O `/livez` com `commit:"unknown"` é o detector — funcionou.
  Antes de qualquer disparo: conferir que `/livez` == SHA da develop.

---

## M3 — VEREDITO (2026-08-18)

**Job `f31f5381-c68f-4757-ba75-91b308ebbf04` fechou `completed` com 12/12 épocas** — a primeira
paridade real contra a baseline (TREINO 1 = `args.epochs=12`, provado pelo checkpoint).
Pod morto por consulta fresca 11:51:44Z: **zero pods**, `currentSpendPerHr: 0`.

### O número

`mascara`, teste de 179 imagens, mesmo instrumento nos dois modelos, gabarito CORRIGIDO:

| | precisão | tp/fp/fn | n | IC95% |
|---|---|---|---|---|
| TREINO 1 (rótulo corrompido) | 0,4815 | 13/14/41 | 27 | [0,31–0,66] |
| **TREINO 2 (rótulo corrigido)** | **0,5000** | 13/13/41 | 26 | [0,32–0,68] |
| baseline histórica 14/08 | 0,4375 | 14/18/92 | 32 | [0,28–0,61] |

Contra o D-163: **0,5000 cai na faixa "0,50–0,61 = dentro do ruído". NÃO decide.** Uma caixa de
diferença entre os dois modelos no ponto de operação calibrado — `tp` e `fn` idênticos.

### Mas o ponto 0,55 é uma coincidência de empate

Varredura de limiar, mesmo gabarito, os dois modelos. **T2 vence em 8 dos 9 limiares:**

| thr | T1 prec | T2 prec | Δ |
|---|---|---|---|
| 0,70 | 0,4167 | 0,6250 | +0,21 |
| 0,60 | 0,4762 | 0,6000 | +0,12 |
| **0,55** | 0,4815 | 0,5000 | +0,02 |
| 0,50 | 0,4545 | 0,4483 | −0,01 |
| 0,40 | 0,2903 | 0,4211 | +0,13 |
| 0,30 | 0,1939 | 0,3800 | +0,19 |

Em **thr 0,30 os IC quase não se tocam** (T1 [0,13–0,28] vs T2 [0,26–0,52]) com `tp` **idêntico** (19).
O efeito real não é ganho de acerto — é **colapso de falso positivo**: 2,5× a 3,1× menos caixas
`mascara` erradas com o mesmo número de acertos.

**Mecanismo, medido e não inferido:** o test de v3 tinha 106 `mascara`; o de v6 tem 54 `mascara`
+ 52 `Óculos`. **Exatamente 52 caixas migraram.** O TREINO 1 aprendeu "mascara = máscara OU óculos"
e dispara em óculos. A confusão do T1 mostra `Óculos → mascara`; a do T2, não.

### 🔴 O achado que engole a pergunta

**Os dois modelos são quase cegos.** Nas 6 classes compartilhadas, em thr 0,55: `tp=17`, `fn=204` —
**recall 7,7% nos dois**. `Botas` (34 gt) e `Uso incorreto de mascara` (16 gt): **zero predições dos
dois modelos**. 12 épocas sobre ~400 imagens não produz detector.

**A dicotomia "rótulo ou volume" tinha uma terceira resposta que os dados sustentam: 12 épocas é
pouco demais para responder qualquer uma das duas.** A paridade em 12 foi correta para o controle —
e é justamente por isso que o controle não decide volume.

### Achados novos (defeitos, não opinião)

- 🔴 **`evaluate_challenger_model` promove modelo cego.** As 3 avaliações em `model_evaluations`
  têm `tp=0` **e** `fp=0` em TODAS as classes — zero predições emitidas — e mesmo assim
  `verdict='promote'`, `map50=0`. Vale para o TREINO 1 também. **O avaliador do produto não mede
  nada e aprova tudo.**
- 🔴 **A métrica por classe não é reprodutível pelo produto.** `per_class_eval_split` não existe em
  lugar nenhum do repo: o 0,4375 saiu de um harness offline de 14/08 que não foi versionado. O
  `metrics.json` que o runner sobe tem 157 bytes (`framework`, `epochs`, `r2_key`) — nada por classe.
- 🔴 **`started_at` mente por 8×.** Job diz `started_at=11:44:54` (min_running 0,8) quando o runner
  começou 11:38:43 — 6,4 min reais pelo log. `started_at` é gravado quando o status vira `running`,
  o que só acontece perto do fim.
- ⚠️ `current_epoch=50` com `total_epochs=12` — o campo continua reportando passo, não época.
- ✅ **D2 funcionou:** `jobs/{id}/pod.log` subiu sozinho, 221 KB, 648 linhas. Primeira vez que o
  interior do pod está legível sem pedir nada a ninguém.

### 💰 Custo — e um erro meu, registrado

`actual_usd` segue **null**. Duração real do runner: **6,4 min** a US$ 0,22/h (`price_usd_h` gravado).

**Erro meu:** registrei antes que "billing do RunPod responde HTTP 400". Respondia **401**, e a causa
era minha: o arquivo `.rp` guarda `RUNPOD_API_KEY=rpa_...` inteiro e eu mandava o nome da variável
colado no bearer. Com o token correto o GraphQL responde: `clientBalance = 28,7322598647`,
`currentSpendPerHr = 0`. A conclusão sobrevive (**não há endpoint de custo por job**:
`/v1/billing/summary` não existe na especificação REST), mas **a evidência que dei para ela estava
errada** — era o meu cabeçalho, não a API deles. Saldo da conta É legível e é o sensor de custo
que faltava.

### PR aberto — ⛔ não mergeado durante job no ar

**[#416](https://github.com/logikos33/Recognition/pull/416)** — `metrics` do job FUNDE
(`COALESCE(metrics,'{}'::jsonb) || %s::jsonb`), o 5º "dois escritores". Aberto **depois** de o job
fechar e o pod estar morto por consulta fresca, porque mergear dispara auto-deploy do worker — foi
assim que o `f0cc48eb` ficou órfão de vigia.

---

## M4.1 — issues semeadas (2026-08-18)

13 issues: **#417** avaliador cego promove · **#418** harness não versionado *(fechada pelo PR #430)* ·
**#419** `started_at` mente 8× · **#420** `current_epoch` reporta passo · **#421** astro 4.16.19 na
landing (trava o CI de TODO PR) · **#422** credencial `NOME=valor` colada no bearer · **#423** alarme
de recorte (12 épocas/400 imgs não produz detector) · **#424** worker sem watch patterns · **#425**
corrida de deploy `railway up` · **#426** D-165 split degenerado · **#427** D-166 gate de bootstrap ·
**#428** Excluir→arquivar · **#429** contradição de 14/08 *(não perseguir)*.

## M5 — Orin (2026-08-18)

🔴 **Retenção do DVR = 4 dias, MEDIDA. A gravação de 31/07 está PERDIDA.**
Mais antigo no gravador: **14/08 06:55**, uniforme nos 7 canais amostrados. Disco 100% cheio
(`UsedBytes == TotalBytes`, ~3,9 TB nas 4 partições) → FIFO sobre pool compartilhado, ~1 TB/dia.
Janela 25/07–05/08 devolve vazio. O `days=8` do minerador era otimista por 2×, e falhava **sem erro**.
→ **PR #431**, D-172.

✅ **Nitidez: limiar 150 fica.** Medido por faixa de hora com a função de produção sobre **834
recortes**: 05–16h **3,8%** · 17–19h **9,2%** · 20–23h **6,9%** · total **5,2%**. **Nenhuma faixa
colapsa** — o medo de "à noite rejeita tudo" está descartado. Crepúsculo é a faixa mais difícil
(mediana 477), o que reforça "leve mas nunca zero". → D-173.
⚠️ Medido sobre acervo do coletor ao vivo, não sobre replay do DVR — re-medir na 1ª mineração real.

Box: 56 GB livres de 116 GB (50%), reserva intacta, up há 19 dias.

## M6 — o plano muda por causa do M5

**A janela é de 4 dias, não 8** — e ela **se renova inteira a cada 4 dias**. Isso muda a natureza do
trabalho: ⛔ não é campanha que se roda uma vez, é **coleta contínua**. Um plano mensal mineraria 4
dias e encontraria vazio nos outros 26.

Faixas (inalteradas): 05–16h e 20–23h cheias · 17–19h leve mas **nunca zero** · ⛔ 01–03h fora ·
250 é **alvo**, não cota · dedup contra o acervo inteiro · respeita `excluida` · retomável.
