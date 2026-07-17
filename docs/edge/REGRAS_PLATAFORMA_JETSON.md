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
- **DeepStream:** versão TEM que casar com o JetPack (**7.1** p/ JP6.2; 8.x/9.x = Jetson Thor/JP7). O **`.deb` do NGC
  exige login** (wget cru pega HTML) → NGC CLI com API key, ou browser+scp. Pré-stagear no provisionamento de campo.
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

## 6. Reuse-first (princípio permanente no box)

Antes de criar/baixar/treinar QUALQUER coisa no Jetson: **inventariar o que já existe**
(`~/jetson-experiments/`: engines, parsers, configs, mediamtx+pacers, telemetria, venvs,
datasets) e REAPROVEITAR. Recriar do zero só quando o inventário provar que não há artefato
equivalente. Os artefatos da campanha de escala e do cenário multi-módulo (mm/) são a base:
novos experimentos DEVEM partir deles (`run_mm.sh`, `gen_mm_app.sh`, sampler etiquetado).
