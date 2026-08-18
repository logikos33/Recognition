# D-093 · Propagação semeada roda no EDGE por padrão (DEV) — guard de datas chaveia por destino

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**11/08 · Vitor (decisão) + Claude (execução) · ✅**

Até aqui, a propagação semeada (DINOv2+SAM, "buscar imagens iguais") só rodava em pod RunPod
(nuvem de terceiro) — por isso as **216 anotações de operação real** (não-encenação) nunca
puderam virar semente: o guard fail-closed de datas existe especificamente porque a imagem
SAI da Logikos rumo a uma GPU de terceiro, e mandar footage real de cliente pra fora nunca foi
aceitável. Decisão: **rodar no Jetson do próprio site por padrão** (DEV) — como a imagem nunca
sai do site, a razão de ser do guard deixa de existir e o acervo de operação vira semente
válida. RunPod continua existindo, só que agora para **treino**, não mais como único destino
da propagação.

- **Guard por DESTINO, nunca por flag.** `app/constants.py::OFFSITE_PROVIDERS`
  (`runpod`/`vast_ai`/`colab`) vs `ONSITE_PROVIDERS` (`edge`/`local`) — união cobre o
  `GpuProvider` inteiro, checada na IMPORTAÇÃO do módulo (um provider novo sem classificação
  derruba o boot, fail-closed, nunca passa despercebido). `propagation_jobs.gpu_provider`
  (migration 116) grava o provider RESOLVIDO na criação; o **guard de datas**
  (`domain/services/propagation_pool.py::validate_pool_frames`, parâmetro
  `enforce_date_guard`) só se aplica quando offsite — tenant/câmera/r2_key continuam validados
  sempre, nos dois destinos (só a checagem de `captured_at` é que cai).
- **Rechecado no DISPATCH, não só no create.** `dispatch_propagation` relê `gpu_provider` DO
  JOB (nunca confia no que foi decidido na criação) — um job criado como edge cujo provider
  fosse trocado pra `runpod` entre os dois momentos faz o guard de data valer de novo e abortar
  sozinho, ao invés de mandar silenciosamente pra nuvem de terceiro o que só foi aprovado pro
  onsite. Testado nos dois sentidos (par obrigatório): job edge com frame de data de operação
  passa create+dispatch; o MESMO job com `gpu_provider` trocado pra `runpod` aborta no dispatch.
- **Resolução do provider:** `provider` explícito no request > env `PROPAGATION_GPU_PROVIDER` >
  default `runpod` (retrocompat — nenhum tenant que já usa a nuvem de terceiro muda de
  comportamento). DEV passa a ter `PROPAGATION_GPU_PROVIDER=edge` como configuração de
  ambiente, não como mudança do default de código.
- **Dispatch pro edge** vira um `edge_commands` (`command_type='run_propagation'`) pro site do
  tenant — resolvido automaticamente se houver exatamente 1 `edge_site` `status='active'`;
  zero sites ou mais de um exige `site_id` explícito no create (erro legível, nunca um palpite).
  O `edge-sync-agent` (`command_poller.py`) lança o MESMO executor
  (`training/propagate_seeded.py`, sem nenhuma mudança de lógica) como uma unit
  `systemd-run --user --scope`, orçada (`MemoryMax=6G`/`CPUQuota=400%` — live view do box nunca
  pode ser espremido). Envs (inclusive `CALLBACK_TOKEN`) só existem num arquivo `0600`, nunca em
  argv/log — `systemd-run --scope` não injeta ambiente (não tem `ExecStart`/`Environment=`
  próprios, herda do processo que o invocou), então o lançamento é um wrapper
  `bash -c 'set -a; . env; exec python executor'`.
- **Landmine real do box (achado do agente de hardware, mesma task):** a wheel torch 2.11
  jp6/cu126 precisa de `LD_LIBRARY_PATH` apontando pro `nvidia/cu12/lib` do venv +
  `/usr/local/cuda/lib64` ANTES de `import torch`, senão `libcudss.so.0: cannot open shared
  object` mesmo com `nvidia-cudss-cu12` instalado — registrado em
  `docs/edge/REGRAS_PLATAFORMA_JETSON.md` §3.5, replicado no arquivo de env que o
  `command_poller.py` escreve (`_derive_ld_library_path`, descoberto via `glob` no venv real).
  Números medidos no box: DINOv2 forward 0,39s + SAM predict 2,57s por imagem 704×480, pico
  CUDA 2,9GB, GPU 99%, live view intocado com o budget acima.
- **Sem watchdog Celery bloqueante** pro edge (diferente do RunPod) — o job fica `running` e a
  conclusão chega assíncrona via callback HTTP do próprio executor no box. Timeout honesto:
  `tasks/gpu_reconciler.py::reconcile_edge_propagation_timeouts` (beat, 5 min) marca `failed`
  um job `running` há mais que `EDGE_PROPAGATION_TIMEOUT_SECONDS` (default 7200s = 2h) sem
  callback final — não há pod pra matar, só honestidade de estado.
- **UI:** `PropagationStatusBar`/`SimilarSearchPanel` mostram "processando no equipamento da
  fábrica — as imagens não saem do site" e escondem custo/GPU quando `gpu_provider` é onsite
  (exposto no GET do job e no preflight). Fases de preparo (cold start de GPU, carregar modelo)
  colapsam numa única "Preparando referências (N caixas)" — sem cold start no box. **Desvio
  documentado do desenho original de 4 fases:** o executor não emite nenhum stage de "refino"
  separado — a UI nunca inventa uma fase sem sinal real por trás.
- **Migrations 116** (`propagation_jobs.gpu_provider`, `ADD COLUMN IF NOT EXISTS`) — sem
  colisão de numeração (115 era a última no momento).
- **Segue pendente / follow-up sugerido:** ADR dedicado (padrão da casa) se o Vitor quiser o
  "porquê longo" documentado à parte deste registro.
