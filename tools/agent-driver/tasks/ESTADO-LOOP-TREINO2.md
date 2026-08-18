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
