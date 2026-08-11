# ADR-0062 — RunPod substitui Vast.ai; runner genérico de job GPU com 3 camadas de garantia de morte

**Status:** Aceita (2026-08-10) · **Autor:** Vitor Emanuel (Logikos) · **Estende:** ADR-0038
(Vast.ai provisioning real — SUPERSEDIDA por este ADR), ADR-0039 (abstração TrainingCompute),
ADR-0044 (detector RF-DETR/YOLOX plugável, licença Apache).

## Contexto

`infrastructure/gpu/vast_client.py` (cliente REST `console.vast.ai/api/v0`) nunca entregou um
treino real em produção — a API deu 404 quando exercitada de verdade. O caminho inteiro
(`_dispatch_vast_ai` → `_run_vast_remote_training` → `_watch_vast_job`) era bem testado
(unitariamente) mas nunca validado ponta a ponta contra a Vast.ai real. Decisão do dono: deletar o
cliente Vast.ai e substituir por RunPod (REST v1 `https://rest.runpod.io/v1` + preço via GraphQL
`https://api.runpod.io/graphql`), generalizando o dispatcher pra um **runner genérico** reusável por
qualquer tipo de carga GPU — hoje só "train", com "propagate" chegando num PR futuro.

Pods RunPod **não têm auto-terminate nativo** — ao contrário do modelo de aluguel por oferta da
Vast.ai (instância efêmera com onstart), um pod RunPod fica rodando (e cobrando) até alguém
explicitamente terminá-lo. Isso move a responsabilidade de "nunca vazar GPU paga" pra nós, em
camadas redundantes — ver Decisão.

## Decisão

### 1. Vast.ai deletado, não migrado

`infrastructure/gpu/vast_client.py` (cliente), `VastAiProvider` (training_compute.py),
`VAST_API_KEY`/`VAST_AI_API_KEY` (gate de `gpu_enabled` em `job_handlers.py`), `VAST_PRICE_CAP` e a
dependência `paramiko` (SSH — órfã, de um fluxo Vast ainda mais antigo, nunca usada pelo cliente REST)
foram removidos. `GpuProvider.VAST_AI` permanece no enum só por linhagem de dados (jobs antigos com
`gpu_provider='vast_ai'` no banco); nenhum dispatch novo usa esse valor. A integração admin
"vast_ai" (`domain/services/integration_service.py`, tipo de credencial por-tenant) foi
**preservada intacta** — é um vault genérico de credenciais de terceiros, não acoplado ao cliente
deletado, e mexer nela cascateava pra mudanças de frontend fora do escopo desta task.

`training/vast/remote_train.py` (o executor self-contained que roda NA GPU remota — treina
RF-DETR/YOLOX, exporta+valida ONNX, sobe via presigned PUT, faz callback por época) foi
**preservado e reusado como está**, no mesmo caminho (`training/vast/`) — é agnóstico de provedor
GPU, só o nome do diretório é histórico.

### 2. Runner genérico (`infrastructure/gpu/`)

- `runpod_client.py` — HTTP puro (`requests`), zero SDK `runpod`: `create_pod`, `get_pod`,
  `list_pods`, `terminate_pod`, `get_gpu_price` (GraphQL), `get_billing`. `resolve_runpod_api_key`
  replica a precedência do antigo `resolve_vast_api_key` (integration store do tenant → env
  `RUNPOD_API_KEY`).
- `runpod_runner.py` — o ciclo de vida (preço → teto de custo → onstart → create_pod → persistir
  `gpu_instance_ref` → watch → terminate SEMPRE → billing) é escrito **uma única vez**
  (`run_runpod_job`) e parametrizado por `JobKind` ("train" | "propagate"). O ponto de injeção
  (executor_source + env livres + callbacks de poll/persist/verify) é genérico — testado com um
  executor dummy e `kind="propagate"` (`tests/.../test_runpod_runner.py`), sem nenhum código novo
  necessário quando a carga "propagate" chegar de verdade.
- `license_gate.py` — trava RF-DETR (ver seção dedicada abaixo).
- `queue/tasks/gpu_reconciler.py` — reconciliador celery-beat (camada 3, ver abaixo).

### 3. Três camadas de garantia de morte

Redundância deliberada — cada camada cobre o ponto de falha da anterior:

1. **No pod** (`runpod_runner.build_onstart`): o executor roda sob `timeout $RUNPOD_MAX_SECONDS` e
   um `trap ... EXIT` que SEMPRE tenta `DELETE /v1/pods/$RUNPOD_POD_ID` antes de sair — sucesso,
   erro ou timeout. Trade-off aceito conscientemente: `RUNPOD_API_KEY` precisa estar no ambiente do
   próprio pod pro trap se autodestruir (só permite gerenciar pods da conta, nunca dados do
   tenant/R2, que viajam via presigned URLs à parte).
2. **Watchdog Celery** (`run_runpod_job` + `_watch`): poll com deadline — deadline estourado, pod
   "morto" 3 polls seguidos, ou status terminal no DB → `client.terminate_pod` SEMPRE roda no
   `finally`, mesmo se o watch levantar.
3. **Reconciliador celery-beat** (`tasks/gpu_reconciler.py`, a cada 5 min, registrado em
   `SAFE_BEAT_SCHEDULE`): varre todos os pods da conta (prefixo `recognition-`) e termina qualquer
   um (i) de job em estado terminal no DB, (ii) mais velho que o deadline do tipo de carga, ou
   (iii) sem job correspondente (`gpu_instance_ref`) no DB. Estado 100% do Postgres — sobrevive a
   restart da API/worker, diferente das camadas 1 e 2. Limitação conhecida: só enxerga a conta cuja
   chave é `RUNPOD_API_KEY` (env, plataforma) — uma chave por-tenant configurada no futuro via
   integration store precisaria de extensão multi-conta.

### 4. Custo: estimativa antes, teto por tipo de carga, real depois

Antes de criar o pod: consulta o preço da GPU (GraphQL `gpuTypes.lowestPrice`), estima
`preço/h × timeout/h`, e recusa o disparo (`CostCapExceededError`, pod **nunca criado**) se exceder
o teto do tipo de carga — `RUNPOD_MAX_USD_TRAIN`/`RUNPOD_MAX_USD_PROPAGATE`, default $2,00 cada
(decisão do dono). Depois do término, consulta billing best-effort e grava estimado/real/gpu_type/
preço em `metrics["gpu_cost"]` (mesmo campo JSONB de métricas de treino, sem migration nova). GPU
default: RTX 4090 community (`RUNPOD_GPU_TYPE`, configurável).

### 5. Trava de licença RF-DETR (ADR-0044, decisão do dono)

O pacote `rfdetr` publica variantes Apache 2.0 (Nano/Small/Base/Medium) e variantes XLarge/2XLarge
sob PML 1.0 (exigem `pip install rfdetr[plus]`) — **não** Apache. `license_gate.py` valida
`base_model`/`hyperparams` do job ANTES de qualquer chamada de rede e rejeita qualquer variante
fora do allowlist `{nano, small, base, medium}` com mensagem legível. Hoje é defesa em
profundidade — `remote_train.py::train_rfdetr` sempre usa `RFDETRBase()` fixo, nenhuma seleção de
variante chega até lá ainda — mas existe ANTES da UI/API exporem seleção, pra nunca depender de
lembrar de adicioná-la depois.

## Consequências

- Zero SDK `runpod` no caminho servido (`requests` puro) — mesma filosofia AGPL-zero/dependência
  mínima do resto do projeto.
- A garantia de morte agora é redundante em 3 camadas independentes, ao custo de mais superfície de
  código — aceito porque o modelo de cobrança do RunPod (sem auto-terminate) torna "nunca vazar GPU
  paga" um requisito de segurança financeira, não só qualidade.
- O reconciler só gerencia a conta de plataforma — uma extensão multi-tenant de chaves RunPod
  precisará estender `tasks/gpu_reconciler.py` (documentado como limitação conhecida, não como bug).
- Nunca validado contra a API RunPod real em produção (mesmo ponto cego que a Vast.ai tinha antes de
  ser descoberto) — o próximo passo pós-merge é um disparo real controlado (1 job barato, teto
  baixo) antes de confiar o fluxo pra qualquer tenant real.
