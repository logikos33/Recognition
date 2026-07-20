# Regras de Plataforma + Pesquisar-antes-de-Instalar — Jetson (edge)

> **Para o Claude Code (e humanos):** antes de instalar QUALQUER coisa no Jetson, ler isto. Objetivo: **não
> instalar pacote/versão errada e não gerar retrabalho.** Companion da `docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md`
> e do `docs/edge/STATUS_2026-07-16_jetson_handson.md`. **C-04: validar sempre no box real, nunca assumir.**
>
> ### 📖 DOCUMENTO VIVO — regra permanente (consultar SEMPRE + alimentar SEMPRE)
> **1. Consultar:** toda vez que for criar/instalar/configurar QUALQUER coisa pro Jetson (nesta sessão ou no
> Claude Code), este documento é leitura obrigatória antes de agir.
> **2. Alimentar:** todo aprendizado novo de plataforma — versão que casa, landmine, fonte oficial, pacote certo
> vs errado, comando de verificação — **deve ser ADICIONADO aqui na hora** (com data + fonte + porquê), antes de
> fechar a task. Aprendeu aqui no chat ou o Code aprendeu rodando → entra neste doc.
> **Por quê:** esta é a **base de conhecimento reutilizável de edge da Logikos** — cada cliente novo (Jetson)
> começa daqui, sem redescobrir os mesmos tropeços. Não deixar aprendizado só no chat/na task; consolidar aqui.

## 0. Regra de ouro
Antes de `apt install` / `pip install` / `docker pull` no Jetson:
1. **Confirmar a plataforma** (arquitetura + JetPack/L4T + CUDA) — §1.
2. **Pesquisar na fonte oficial** e **casar a versão** pela tabela de compatibilidade — §2. Nunca usar pacote/wheel
   genérico de **x86** nem de **ARM-SBSA** (servidor). O Jetson é **ARM Tegra / L4T** com **iGPU**.
3. **Verificar depois de instalar** que funciona de verdade no box (ex.: enxerga a iGPU) — §4.
4. **Registrar** o que instalou, a versão e a fonte — §5.

## 1. Verdade da plataforma (deste box — reconfirmar, não decorar)
| Item | Valor |
|---|---|
| Modelo | NVIDIA Jetson Orin NX Super 16GB (Palit Pandora), hostname `pandora` |
| Arquitetura | **aarch64 / Tegra** (NÃO x86, NÃO ARM-SBSA) |
| JetPack / L4T | **6.2 / r36.4.3** · Ubuntu 22.04 · kernel 5.15.148-tegra |
| CUDA / cuDNN / TensorRT | **12.6 / 9.3 / 10.3** (via `nvidia-jetpack`) |
| DeepStream | **7.1** (casa com JP6.2) |
| GPU | iGPU Ampere + **2× DLA** + PVA + NVDEC/NVENC |
| Disco / Power | NVMe 116G · modo **40W** (MAXN Super) |
| Rede | NIC real **`enP8p1s0`** (não `eth0`) · SSH `pandora@100.93.126.76` (Tailscale) |
| Tela | monitor físico: `DISPLAY=:1`, `XAUTHORITY=/run/user/1000/gdm/Xauthority` |
> Comandos de conferência: `cat /etc/nv_tegra_release` · `uname -m` · `nvcc --version` · `deepstream-app --version-all`.

## 2. Onde pesquisar (fontes autoritativas — sempre casar a versão)
- **Compatibilidade NVIDIA (obrigatório antes de escolher versão):** a **tabela de compatibilidade do DeepStream**
  (DS ↔ JetPack ↔ L4T ↔ CUDA ↔ TensorRT), o **JetPack SDK page** e as **L4T Release Notes**.
- **PyTorch/ML no Jetson:** **jetson-ai-lab** (índice pip jp6) e os **containers dusty-nv** (`dustynv/l4t-pytorch`,
  `l4t-ml`) — já vêm buildados pra L4T com iGPU.
- **Ubunto base (o que o próprio sistema recomendou):** `help.ubuntu.com` (docs) e **`ubuntu.com/pro` / ESM**
  (patches de segurança do sistema "minimized" — 300+ pendentes; aplicar de forma controlada, sem tocar `nvidia-l4t-*`).
- Regra: se a fonte não diz explicitamente "**L4T / Jetson / JetPack 6.x**", **desconfie** — provável build errado.

## 3. Landmines já aprendidas (NÃO repetir)
- **PyTorch:** o torch **genérico do PyPI / SBSA NÃO enxerga a iGPU do Jetson** (`torch.cuda.is_available()==False`).
  → usar **container dustynv (`l4t-pytorch`, tag r36.4)** ou **wheel do índice Jetson (jetson-ai-lab / jp6, CUDA 12.6)**.
- **DeepStream:** versão TEM que casar com o JetPack (**7.1** p/ JP6.2 Orin; **8.0 = Thor-only** SM90 — falha em
  Orin SM87; **9.1** (jul/2026) volta a suportar Orin **mas exige JP7.2** — ver matriz e baseline congelada em §8).
  O **`.deb` do NGC exige login** (wget cru pega HTML) → NGC CLI com API key, ou browser+scp. Pré-stagear no
  provisionamento de campo.
- **iptables:** usar **nft** (`update-alternatives --set iptables /usr/sbin/iptables-nft`), não legacy. O **kernel
  L4T vem sem alguns módulos netfilter** → afeta roteamento/firewall (subnet das câmeras); não assumir iptables completo.
- **Ubuntu "minimized":** ferramentas básicas faltam (`nano`, `gst-inspect`…). Instalar **pontualmente** o que faltar,
  conforme o inventário mostrar o gap — nunca no chute.
- **Rede:** NIC é **`enP8p1s0`** — scripts não podem hard-codar `eth0`.
- **Nunca** `apt upgrade` em bloco às cegas (risco nos pacotes `nvidia-l4t-*`).
- **Segredos** (API keys) → em `~/.../.env` com `chmod 600`, lidos do arquivo. **Nunca** no chat, no histórico do
  shell (`echo`) nem no git (`.gitignore`).

## 4. Checklist pré-instalação (rodar SEMPRE)
- [ ] `uname -m` = `aarch64`? Confirmar Tegra/L4T (não SBSA/x86).
- [ ] Versão do artefato **casa** com JetPack 6.2 / CUDA 12.6 / L4T r36.4 (checou a tabela oficial)?
- [ ] Fonte é **NVIDIA/L4T/jetson-ai-lab/dustynv** (não PyPI/apt genérico)?
- [ ] Download grande → dentro de **tmux** (link pode cair) e persistente.
- [ ] **Pós-install: verificar que funciona no box** (ex.: `torch.cuda.is_available()` True + device; `deepstream-app --version-all`).

## 5. Registro obrigatório (para não perder e ser reproduzível)
Todo install / decisão / achado de campo → **registrar** na task correspondente **e** no doc de status/achados
(`docs/edge/STATUS_*` / `EXPERIMENTOS_*`), com **versão + fonte + porquê**. É o que torna o provisionamento da RVB
(task-097) reproduzível sem redescobrir cada landmine. Ver a disciplina de histórico na diretriz de operação.

## 3.1 Landmines dos experimentos 2026-07-16 (treino YOLOX + stress 28 cams)
- **Torch no Jetson (crítico):** wheel **SBSA torch 2.13** (download.pytorch.org) **exclui sm_87 (Orin)** →
  `cuda.is_available()==True` mas todo kernel falha (`no kernel image`). Usar **torch 2.11 do jetson-ai-lab
  `jp6/cu126`** (o índice `.dev` está com DNS quebrado no box → usar `.io`).
- **Conflito de cuBLAS:** torch 2.11 puxa `nvidia-cudss-cu12`, que arrasta **libcublas SBSA 12.9** e quebra
  (`CUBLAS_STATUS_ALLOC_FAILED`). Fix: `pip uninstall nvidia-cublas-cu12` (a de sistema /usr/local/cuda serve).
- **Preproc YOLOX moderno = BGR 0–255 SEM normalização** → DeepStream `net-scale-factor=1.0` +
  `model-color-format=1`. O `0.0039` (1/255) do config antigo **zera as detecções silenciosamente**.
- **`ulimit -n` 1024 estoura com ~28 streams** (cada surface NVMM é fd dmabuf → `NVMAP_IOC_GET_FD failed`) →
  `ulimit -n 65535` antes do `deepstream-app` (hard = 1048576, sem sudo).
- **DLA-clean IMPOSSÍVEL no grafo YOLOX atual:** 113 camadas (decode/grid: CONSTANT/CAST/ELEMENTWISE/SHUFFLE/
  POOLING) caem pra GPU. GPU-only fp16 **465 qps** vs DLA+fallback **103 qps** (4,5× pior). DLA só vale com export
  "decode fora do grafo".
- **RTSP sintético sem sudo:** MediaMTX (binário arm64) + pacer Python — `rtspclientsink` ausente no gst do box;
  multi-uri `%d` do deepstream-app é **0-based** (`cam0`…).
- **Export torch 2.11:** `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` p/ ckpt; `torch.onnx.export` (dynamo) exige
  `onnxscript` e salva pesos em `.onnx.data` externo.
- **`/usr/bin/time` ausente** (Ubuntu minimized) → medir RAM de pico pela telemetria (task-100).

## 3.2 Landmines da campanha de escala 2026-07-17 (tasks 105/106)
- **Fan: tach NÃO ligado neste hardware** — PWM 255 com RPM 0 e a fan GIRANDO (verificação física do
  Vitor). Health-check de fan aqui = PWM + curva térmica, **nunca RPM**. Perfil default `quiet`.
- **Fluidez de boxes = `interval=N` + nvtracker NvDCF** (`config_tracker_NvDCF_perf.yml` do sample).
  Boxes suaves a full-FPS via tracker E ~-35% GPU / -2 W (4 cams). É a maior alavanca de escala.
- **Teste de fluidez exige fonte ≥30 fps** — vídeo gerado a 5 fps vira o teto e mascara tudo.
- **Engine batch dinâmico 1..40 leva ~24 min** de build no Orin NX (fp16, opt=28). Buildar em tmux.
  Batch-28: 19,3 qps = **539 inf/s** (vs ~250 inf/s no caminho nvinfer batch-1) → batch é ~2× no throughput.
- **RF-DETR (pesquisa 2026-07-17):** só Nano/Small/Medium/Large são Apache (XL/2XL = PML 1.0, proibidas).
  Export = `dets` [B,Q,4] cxcywh normalizado + `labels` [B,Q,C] logits, sem NMS → `cluster-mode=4`;
  preproc ImageNet RGB (`net-scale-factor=0.01735`, `offsets=123.675;116.28;103.53`) — DIFERENTE do
  YOLOX (BGR 0-255 raw). Transformer NÃO roda em DLA (attention/LayerNorm). INT8 em DETR não compensa.
  Parser próprio: `~/jetson-experiments/rfdetr-parser/` (`NvDsInferParseCustomRFDETR`).
- **Pacer UDP single-process satura ~600 frames/s agregados** (granularidade do asyncio.sleep) e
  FAMINTA os streams silenciosamente — GPU baixa + FPS baixo = suspeitar da FONTE, não do box.
  Validar sempre com decode-only (gie enable=0). Fix: shard em N processos (8 streams/proc, burst=4)
  → 40×480p30 = 31,6 FPS/stream limpo. (`pacer_shard.py`)
- **Tiler compõe MESMO com fakesink** — headless de verdade exige `[tiled-display] enable=0`
  (+4 FPS/stream a 40 cams). OSD e `batched-push-timeout` são ~neutros.
- **nvinfer batch grande em fontes live = stall**: batch-40 (76 ms) a cada N batches segura o
  pipeline e o decoder dropa (`OutputBufferUnavailable`). Fix: **sub-batch** (nvinfer `batch-size`
  8–16 < batch do mux) → +4 FPS/stream. Regra: latência da inferência << período entre inferências.
- **Checkpoint YOLOX-Nano 0.1.1rc0 (2021) é INÚTIL como detector demo** — objectness baixíssimo,
  KITTI sai 100% vazio com preproc correto (confirmado 2x). Para demo de carros usar o
  **TrafficCamNet do próprio DeepStream** (`Primary_Detector/resnet18_trafficcamnet_pruned.onnx`);
  1ª execução builda engine INT8 b30 (~5 min) — esperar antes de medir.
- **Config ótima multi-stream (campanha 2026-07-17):** interval=3–4 + NvDCF + sub-batch + headless →
  28 cams: 29 FPS/stream (GPU 42%) · 40 cams: 22,4 (GPU 65%) · ambos ≥5,6 inf/s/cam. 40 cams VIÁVEL.
- **INT8 PTQ com calibração real VALE em CNN** (300 imgs train, entropy): 40 cams 24,9 FPS com
  **GPU 45%** (fp16: 22,4 @ 65%). Build via TRT python exige `parser.parse_from_file` quando o ONNX
  tem pesos externos (`.onnx.data`). Validar mAP do engine INT8 antes de produção. Em DETR, NÃO vale.
- **RF-DETR no DeepStream:** preproc ImageNet RGB + `cluster-mode=4`; parser próprio em
  `~/jetson-experiments/rfdetr-parser/`. Batch em transformer escala pouco (+21% b8 vs +115% CNN).
  Teto Nano no Orin NX: ~172 inf/s → ~20 cams @5 inf/s. `rfdetr[train,loggers]` p/ treinar (não
  clobbera o torch Jetson — verificado).

## 3.3 Landmines do cenário multi-módulo 2026-07-17 (tasks 107/111)

- **`interval` do nvinfer é IGNORADO no caminho `input-tensor-from-meta`** (nvdspreprocess/ROI):
  int0 ≡ int4 (medido 2×: GPU 99% nos dois). O preprocess tensoriza TODO frame. A cadência de
  inferência por ROI se controla no DECODER: **`drop-frame-interval=N` no [sourceX]** do
  deepstream-app (drop=5 → 6 inf/s/ROI; decode segue 30 fps, honesto).
- **Múltiplas instâncias deepstream-app conectando RTSP ao mesmo tempo = streams mortos
  SILENCIOSOS** (fps 0.00 no PERF, zero erro no log). Fix: `rtsp-reconnect-interval-sec=10`
  nos sources + stagger de ~2 s entre lançamentos de instância. Sempre validar `fps_min>0`.
- **Mutter (GNOME) ignora `window-x/window-y` do sink EGL** — janelas caem todas em (0,0).
  Sem sudo p/ xdotool/wmctrl: `pip3 install --user python-xlib` e mover via
  `w.configure(x=,y=)` (script no `mm/screen_mm.sh`). Tamanho é respeitado, posição não.
- **YOLOX-Tiny COCO 0.1.1rc0 (dez/2021) FUNCIONA** (13,3k detecções KITTI com conteúdo,
  car/truck conf 0,3–0,93) — a landmine do "checkpoint 2021 dud" é **específica do Nano**,
  não do release inteiro. Releases 0.2.0/0.3.0 do Megvii NÃO têm assets; os pesos oficiais
  vivem no 0.1.1rc0.
- **heredoc `<<EOF` (não-quotado) via ssh dentro de aspas simples expande `$var` no shell
  REMOTO** — patches python com strings contendo `$` corrompem silenciosamente. Usar `\$`
  ou heredoc quotado (`<<'EOF'`).
- 4 instâncias DS + 28 decodes (26×480p + 2×4MP) + preprocess ROI: RAM total ~8,1 GB de 16 —
  multi-processo por grupo cabe com folga; engines compartilham o mesmo arquivo `.engine` em
  leitura sem conflito.

## 3.4 Landmines do soak co-residência RVB 2026-07-18 (task-113)

Objetivo da task: provar que a stack COMPLETA (Redis+Postgres+API+3 módulos de inferência) roda
co-residente por horas sem travar, e embarcar a RVB. Veredito **GO** (soak 4.8h). Detalhe em
`docs/edge/SOAK_RVB_2026-07-18.md`; harness versionado em `deployments/edge/soak113/`.

- **`pgvector` do conda-forge ARRASTA UPGRADE do Postgres 16→18 (landmine de restart/reboot):**
  instalar `pgvector` no env conda subiu o binário postgresql p/ **18.4**. O postmaster 16 já rodando
  seguiu servindo o soak inteiro (não reiniciou), **mascarando** o problema; no **restart/reboot** o
  binário 18 sobe contra data dir 16 → `FATAL: database files are incompatible ... version 18.4`.
  **Só aparece no restart, não em runtime.** Fix: `micromamba remove pgvector` + `micromamba install
  postgresql=16.14` (data preservado). Regra: **nunca co-instalar pacote que arraste upgrade de major
  do Postgres num env com data dir existente — pinar a major.** (`pgvector` do conda vem p/ PG18.)
- **Sem sudo no box (execução autônoma):** `sudo` exige senha; bloqueia apt, jetson_clocks, nvpmodel,
  sysctl, swap em disco, systemd de **sistema**, reboot, docker-group. → registrar pendência, seguir.
- **Postgres/Redis co-residentes SEM sudo:** Redis = build do source (`make`); Postgres = **micromamba**
  (binário estático, sem sudo) + `-c conda-forge postgresql=16`. `pgserver`/`postgresql-wheel` do pip
  **não têm wheel aarch64**.
- **API precisa de Python 3.11** (`from enum import StrEnum`); sistema só tem 3.10 → `micromamba create
  -n api -c conda-forge python=3.11` + `pip install -r requirements/api.txt` (wheels aarch64 OK).
- **Budget de memória por serviço SEM sudo:** cgroup v2 com controllers `memory pids` **delegados ao
  user slice** → `MemoryMax/MemoryHigh` em unit `systemctl --user`. **Ordenação de OOM sem sudo:**
  `OOMScoreAdjust` **positivo** (mais matável) não exige privilégio → auxiliares morrem antes do
  pipeline DeepStream (que fica em 0). **`Linger=yes`** já ativo → units --user sobrevivem a disconnect
  e reboot (`Restart=always` + `WantedBy=default.target`).
- **Docker NÃO usável sem sudo:** socket é root:docker e `pandora` fora do grupo → `permission denied`.
- **PSI indisponível** (`/proc/pressure/*` não existe — kernel sem `CONFIG_PSI`): inferir pressão por
  `pswpin/pswpout` (delta `/proc/vmstat`) + `MemAvailable`. **dmesg restrito** (`dmesg_restrict=1`):
  OOM só via `systemd Result=oom-kill` + `NRestarts`, não pelo kernel log.
- **Swap é zram-only** (8×1GB comprimido) — não NVMe. Risco p/ alocações grandes; recomendação de
  hardening (sudo do Vitor): swapfile NVMe + `vm.swappiness=10`.
- **`railway_start.py` aponta `--chdir backend/`** que não existe no monorepo → rodar gunicorn de
  `services/api` com `app:create_app()`.
- **Embarque multi-tenant:** API lê **`public.cameras`** (filtrado por `tenant_id`); popular também o
  `{schema}.cameras`. `tenants.schema_name` (não `tenant_schema`) → claim JWT. `deployment_mode` CHECK
  aceita só `cloud|edge|hybrid` — **"dual" = `hybrid`**.
- **Resultado co-residência:** stack de dados/API adiciona só **~400MB** sobre a inferência
  (redis 32 + pg 144 + api 125 + prod/cons 60). RAM regime **~7.8GB/15.6GB**, swap ~0, GPU ~68-76%,
  GPU max 67°C, sem leak (slope −2.6 MB/h em 4.8h). Cold-start da stack inteira: 10/10 em 11s.

## 3.5 Landmines do shootout de Qualidade 2026-07-18 (D-FINE × RT-DETRv4 × RF-DETR)

- **Refs git locais quebradas envenenam `git fetch` (crítico — causou alarme falso):** dezenas de
  `refs/heads/` corrompidas (`worktree-wf_*`, `feat/*`, `mutirao/*`, `wip/*`, `docs/*.lock`) apontando p/ objetos
  ausentes → `fatal: bad object ... / did not send all necessary objects` → **nenhuma ref remote-tracking
  atualiza** e a `origin/develop` local fica PRs atrás sem avisar. Fix: `find refs/heads -type f | git cat-file
  --batch-check | awk '/missing/'` → deletar. **Estado de branch/PR = fetch fresco + `gh`, nunca ref em cache**
  (ver `DIRETRIZ §6.1`).
- **Revive do `train-venv`:** `import torch` falhava com `libcudss.so.0: cannot open shared object` mesmo com
  `nvidia-cudss-cu12` instalado — o `.so` existe mas não está no loader path. Fix (sem reinstalar):
  `export LD_LIBRARY_PATH=$HOME/jetson-experiments/train-venv/lib/python3.10/site-packages/nvidia/cu12/lib:/usr/local/cuda/lib64:$LD_LIBRARY_PATH`
  → torch 2.11, `cuda.is_available()==True`, device Orin. Colocar no wrapper de treino.
- **Instalar frameworks de treino SEM clobberar o torch Jetson:** `requirements.txt` de D-FINE/RT-DETRv4 lista
  `torch`/`torchvision` → reinstala wheel SBSA e quebra a iGPU (§3.1). Fix: constraints pinando o torch do box:
  `printf 'torch==2.11.0\ntorchvision==0.26.0\n' > constraints.txt` + `pip install -c constraints.txt
  faster-coco-eval PyYAML tensorboard scipy calflops transformers loguru`.
- **`wget` ausente** → `curl -fL -o` para checkpoints de GitHub Releases (grandes → em tmux).
- **Batch default OOM-mata DataLoader worker mesmo com 10GB livres:** D-FINE-S custom vem `total_batch_size: 64`;
  co-residente com o soak (4 DeepStream ~76% GPU) o worker leva SIGKILL por contenção de memória unificada. Fix:
  `total_batch_size: 2` + `num_workers: 0`. **Tradeoff medido:** `num_workers=0` deixa o treino **CPU-bound** →
  iGPU faminta (~5% GR3D) e época lenta. Para treino LIMPO/rápido: **pausar as `soak-infer-*`** (voltam por Linger)
  e subir `num_workers`/batch. `total_batch_size`/`num_workers` são indentados 2 espaços — `sed ^    ` (4) falha
  silenciosamente; sempre `grep` os valores efetivos antes de lançar.
- **Resultado (medido, nosso PPE val):** D-FINE-S (Apache, fine-tune Obj365→COCO, 30 ép, 3h07m) **convergiu a
  AP_small ≈ 0.626 / AP 0.776**, superando o RF-DETR Nano (0.565/0.754) no juiz — mas com 3× as épocas do RF-DETR
  (comparação ainda não é justa). Licenças D-FINE/RT-DETRv4 = **Apache-2.0** (RT-DETRv4 destila DINOv3 só como
  teacher no treino). Detalhe em `SHOOTOUT_QUALIDADE_2026-07-18.md`.

## 3.6 Landmines de containerização DeepStream / jetson-containers (pesquisa 2026-07-19)

> **Contexto:** pesquisa Jetson AI Lab + leitura do fonte de `dusty-nv/jetson-containers` (branch `master`,
> lido via `gh api` em 2026-07-19). Estas landmines só mordem quem tenta rodar DeepStream **em container** no
> Jetson — hoje NÃO usamos esse caminho (DS 7.1 é instalação nativa via `.deb`), mas ficam registradas porque
> o container é tentação recorrente e cada uma custou (ou custaria) horas. Fonte de cada item no fim da seção.

- **L1 (crítica) — `jetson-containers` puxa DS 8.0 (Thor-only) em L4T ≥ 36.4.3 e QUEBRA no Orin.**
  `packages/cv/deepstream/config.py` mapeia `if L4T_VERSION >= Version('36.4.3'): DEEPSTREAM_TAR =
  'deepstream_sdk_v8.0.0_jetson.tbz2'`. **Nosso box é exatamente r36.4.3** → cai nesse branch. DS 8.0 é
  **Thor-only (SM 90)**; no Orin (SM 87) o TensorRT rejeita: `Target GPU SM 87 is not supported`. Se for
  usar o package mesmo assim, **forçar `DEEPSTREAM_URL`/`DEEPSTREAM_TAR` do DS 7.1** e **VALIDAR a URL com
  `wget -S --spider <url>` antes de confiar** (a URL do 7.1 é inferida do padrão NGC, não confirmada por
  download). Reportado upstream: `dusty-nv/jetson-containers#1727` (root-cause + fix).
- **L2 — não existe imagem `dustynv/deepstream` para r36.4.** A mais nova publicada é `r36.2.0` (mar/2024).
  O `autotag deepstream` então cai em **build local de ~10 GB** (arrasta tritonserver/opencv/ffmpeg/vulkan).
  Não é caminho de campo — provisionar por `.deb` nativo, não por container.
- **L3 — o gate de compatibilidade JP6 tem fronteira dura em `minor == 4`.** Imagens `r36.2`/`r36.3` são
  **rejeitadas** num host `r36.4.x`. Corolário: **upgrade de JetPack ⇒ rebuild de TODAS as imagens** (não há
  reaproveitamento cross-minor).
- **L4 — `/ssd` (data-root do docker no NVMe) precisa montar ANTES do `docker.service`.** Sem
  `RequiresMountsFor=/ssd` na unit, um reboot sobe o docker antes do mount e ele **quebra silenciosamente**
  (grava no rootfs eMMC/interno, não no SSD).
- **L5 — migrar data-root com `rsync -axPS`, NUNCA `cp -r`.** O overlay2 usa **hardlinks**; `cp -r` os explode
  em cópias e corrompe/incha as imagens. `-a` preserva, `-x` não cruza filesystem, `-S` trata sparse.
- **L6 — em JP6, `apt install nvidia-container` NÃO instala mais o Docker** (mudança vs JP5) — instalar o Docker
  em passo separado. E **`"default-runtime": "nvidia"` no `/etc/docker/daemon.json` NÃO é cosmético**: sem ele o
  `docker build` não enxerga o NVCC/CUDA (builds de estágio CUDA falham).
- **L7 — `install.sh` do jetson-containers instala pip system-wide no Ubuntu 22.04** (só usa venv em 24.04) →
  polui o Python do sistema. **Usar venv manual** antes de rodar o instalador no nosso box (22.04).
- **L8 — container como não-root ⇒ `CUDA error 801`.** Passar **`--group-add <GID NUMÉRICO>`** dos grupos
  `video` e `render` do HOST (não o nome — o nome resolve pro GID do container, que não bate com o do host, e
  falha **silenciosamente**). Descobrir com `getent group video render` no host.

**Fontes:** `github.com/dusty-nv/jetson-containers` (`packages/cv/deepstream/config.py`, `install.sh`, docs de
data-root/daemon.json), issues `#405 #1117 #1721 #1722`, e a matriz de compatibilidade DeepStream da NVIDIA (§8).
Nossa constatação de L1 foi verificada lendo o `config.py` no HEAD do repo (2026-07-19).



Estado atual do `pandora` (produção-like), confirmado por `swapon --show` / `cat /proc/sys/vm/swappiness` /
`systemctl is-enabled,is-active jetson-clocks.service`:

| Item | Estado | Como |
|---|---|---|
| **Swap híbrido (zram + NVMe)** | ✅ persistente | **coexistem** (verificado 2026-07-19): `/swapfile` 16G NVMe **prio −2** (overflow) + 8× zram 978M **prio 5** (rápido, sem desgaste NAND). Sob carga o kernel prefere zram (~1.8G usado) e mal toca o NVMe (~16M) — config ideal p/ inferência 24/7. **Não desabilitar o zram**: a recomendação NVIDIA de tirá-lo mira BUILD de container/modelos grandes, não runtime. |
| **`vm.swappiness=10`** | ✅ persistente | via sysctl (era 60) |
| **`jetson-clocks` no máximo** | ✅ persistente | `jetson-clocks.service` **enabled+active** → reaplica no boot |
| **`nvpmodel` 40W** | ✅ | default do box |
| **Serviços edge (`systemctl --user 'soak-*'`)** | ✅ auto-restart no boot | Linger=yes + units enabled → 10/10 voltam sozinhos |
| **Perfil de fan** | ⚠️ **`quiet` temporário** | reverter p/ **`cool`** antes da carga 24/7 (sudo=Vitor; checklist task-097): `sudo sed -i 's/FAN_DEFAULT_PROFILE .*/FAN_DEFAULT_PROFILE cool/' /etc/nvfancontrol.conf && sudo systemctl restart nvfancontrol` |

> **Nota:** o fan tem **tach NÃO ligado** (§3.2) — health-check de fan = PWM + curva térmica, nunca RPM.

## 6. Reuse-first (princípio permanente no box)

Antes de criar/baixar/treinar QUALQUER coisa no Jetson: **inventariar o que já existe**
(`~/jetson-experiments/`: engines, parsers, configs, mediamtx+pacers, telemetria, venvs,
datasets) e REAPROVEITAR. Recriar do zero só quando o inventário provar que não há artefato
equivalente. Os artefatos da campanha de escala e do cenário multi-módulo (mm/) são a base:
novos experimentos DEVEM partir deles (`run_mm.sh`, `gen_mm_app.sh`, sampler etiquetado).

## 8. Baseline de produção CONGELADA + matriz de compatibilidade (2026-07-19)

> **Regra:** esta é a combinação **congelada** para o go-live RVB. Não fazer upgrade de nenhum componente
> desta linha sem tratar como mudança **P0-CRÍTICO** com plano próprio. C-04: reconfirmar no box (§1).

### 8.1 Baseline congelada

**JP6.2 / L4T r36.4.3 / CUDA 12.6 / cuDNN 9.3 / TensorRT 10.3 / DeepStream 7.1 / Python 3.10 (sistema).**

**Motivo:** é a **última combinação Orin + DeepStream plenamente suportada**. DS 8.0 é **Thor-only** (SM 90); DS
7.1 **não roda em JP7.2** (quebra por ABI GLib/GStreamer — ver §3.6 e histórico). Todos os engines TensorRT do
box (`.engine` INT8/fp16) foram buildados contra **TRT 10.3** e **não são portáveis** para outra major de TRT.

### 8.2 Matriz DeepStream ↔ JetPack ↔ L4T ↔ CUDA ↔ TensorRT ↔ Jetson

| DeepStream | JetPack | L4T | CUDA | TensorRT | Suporte Jetson |
|---|---|---|---|---|---|
| **7.1** ← **NOSSA baseline** | **6.2** | **r36.4.x** | **12.6** | **10.3** | **Orin (Ampere SM 87) ✅** |
| 8.0 | 7.0 | r38.x | 13.x | 10.x | **Thor-only (Blackwell SM 110)** — falha em Orin |
| 9.0 | 7.x | — | 13.x | — | Thor; Orin **não** compatível (incompatível c/ JP7.2 por NVIDIA) |
| **9.1** (rel. 2026-07-14) | **7.2** | **r39.2** | 13.x | 10.13+ | **Orin + Thor ✅ — mas exige JP7.2** |

Fontes: NVIDIA DeepStream Release Notes / Quickstart (docs.nvidia.com/metropolis/deepstream) e fórum NVIDIA
(threads "DS 9.0 compatible with Orin" e "Expected release date of DeepStream 9.1"), consultados 2026-07-19.

### 8.3 DeepStream 9.1 — SAIU, e o que muda

- **Status: LANÇADO em 2026-07-14.** Confirmado na doc oficial (release notes) e cobertura de imprensa
  (MarkTechPost/Blockchain.News, 2026-07-18). Traz multi-view 3D tracking, 13 "agentic skills", auto-calibração.
- **Suporta Orin (Nano/NX/AGX) ✅** — é a **primeira** release pós-8.0 a voltar a suportar Orin. Isso **levanta o
  bloqueio** anterior ("não existe DS com suporte a Orin em JP7.2") que travava o port do edge.
- **PORÉM exige JetPack 7.2 / L4T r39.2.** NÃO é drop-in no nosso JP6.2. Para adotar DS 9.1 é obrigatório fazer o
  **port JP7.2 inteiro** (§8.4). O pacote agora é distribuído por **GitHub Releases** (não mais só NGC).
- **Recomendação (2026-07-19): NÃO fazer upgrade agora.** Manter DS 7.1 / JP6.2 congelado para o go-live RVB.
  Agendar o port JP7.2+DS 9.1 como esforço planejado (agora desbloqueado), não urgente; DS 9.1 tem **dias** de
  vida — deixar amadurecer. Reavaliar quando (a) houver relatos de campo de DS 9.1 estável em Orin NX e (b) o
  RVB estiver em produção estável no baseline atual.

### 8.4 Port JP7.2 = P0-CRÍTICO (semanas) — desbloqueado, não trivial

Migrar para JP7.2 (pré-requisito de DS 8.0/9.1) é reconstrução de plataforma, não upgrade incremental:
Ubuntu **22.04→24.04**, kernel **5.15→6.8**, CUDA **12.6→13.2**, TensorRT **10.3→10.13+**, Python **3.10→3.12**,
e **TODOS os engines TensorRT reconstruídos** (INT8 exige recalibração + re-validação de mAP). Estava **BLOQUEADO
até existir DS com suporte a Orin** — com DS 9.1 (§8.3) o bloqueio caiu, mas o custo (semanas) permanece.

### 8.5 Quantização: o teto do Orin é INT8 (não FP8, não FP4)

- **FP8 exige SM 89+; NVFP4 exige SM 110+.** O **Orin é SM 87 e NÃO tem esses tensor cores.**
- O ganho de quantização disponível no nosso silício é **INT8** (já validado: campanha 2026-07-17, §3.2 — 40 cams
  @ GPU 45%). **Não perseguir FP8/FP4 no Orin achando que é questão de software** — é ausência de hardware. FP8/FP4
  só entram em pauta se/quando migrarmos para Thor (SM 110), o que é outro projeto.
