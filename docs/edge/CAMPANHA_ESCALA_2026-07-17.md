# Campanha de escala e otimização — Jetson Orin NX (tasks 105 + 106) — 2026-07-17

> Objetivo: limite SEGURO do hardware com o MODELO REAL até 40 câmeras, config ótima, fluidez das
> bounding boxes, bench YOLOX × RF-DETR, impacto de rede/Recognition.
> 28 câmeras = produção (RVB) · 40 = expansão (upsell). Execução no box real via SSH, tela física `:1`.
> Baseline: `EXPERIMENTOS_2026-07-16.md` (103/104/101/102).

## Sumário executivo

1. **40 câmeras são VIÁVEIS no Orin NX com YOLOX** acima do alvo de 5 inf/s/câmera. Config
   vencedora = **INT8 calibrado + sub-batch nvinfer + `interval` 3–4 + NvDCF + headless**:
   **40 cams: 24,9 FPS/stream, 6,2 inf/s/cam, GPU 45%, 16,2 W, 57 °C** · 28 cams: taxa cheia
   (31,5 FPS), GPU 47%, 13,9 W. (Perfil `quiet`, clocks dinâmicos — números ainda conservadores.)
2. **Fluidez resolvida**: `interval=N` + tracker NvDCF reproduz a suavidade do sample DeepStream e
   ainda É a maior alavanca de escala (-35% GPU, 3× menos energia na cena densa). Evidência em vídeo.
3. **RF-DETR Nano: +4,4 mAP (75,6 vs 71,2), mas 3× menos throughput** — teto ~172 inf/s → ~20 cams
   a 5 inf/s. DLA impossível (2.303 fallbacks). **Recomendação: YOLOX para 28–40 cams; RF-DETR como
   detector de acurácia para sites menores/câmeras críticas.**
4. **Overhead do Recognition ≈ zero** no pipeline (simulação local); WAN real pendente de câmera.
5. **Fan gira** (tach ausente — PWM como health-check); térmica com folga enorme em carga sustentada.
6. Telemetria completa da campanha em JSONL etiquetado por cenário (base para o gráfico, prompt futuro).
7. Landmines novas alimentadas no `REGRAS_PLATAFORMA_JETSON.md` (pacer, tiler headless, sub-batch,
   nano-2021, ulimit, preproc RF-DETR vs YOLOX).

---

## 1. Fluidez das bounding boxes — ✅ HIPÓTESE CONFIRMADA

**Hipótese do prompt:** o sample DeepStream é suave porque infere em INTERVALO + tracker (NvDCF)
interpolando boxes entre frames; o nosso inferia todo frame sem tracker → jitter + peso.

**A/B no box** (4 tiles, vídeo tráfego 1080p30, engine nano COCO, tela `:1`, OSD full FPS):

| Variante | Config | FPS/stream | GPU | VDD_IN |
|---|---|---|---|---|
| **A (antes)** | `interval=0`, sem tracker | 30 | 57,8% | 9,67 W |
| **B (depois)** | `interval=4` + NvDCF (`config_tracker_NvDCF_perf.yml`) + IDs | 30 | **37,3%** | **7,46 W** |

- Renderização idêntica a 30 FPS; em B as boxes seguem o objeto suavemente (tracker propaga entre
  inferências) e ganham ID persistente — visual igual ao do sample DeepStream.
- **-35% de GPU e -2,2 W** — a fluidez é também a maior alavanca de escala (confirmado o "bônus").
- Evidência: gravações de tela `fluidez_rec_A.mp4` / `fluidez_rec_B.mp4` (12 s cada) + screenshots
  em `~/jetson-experiments/artifacts/`. Config: `[tracker]` + `interval=N` no `[primary-gie]`
  (`~/jetson-experiments/fluidez/gen_app.sh`).

**Nota de método:** a 1ª tentativa de A/B usou o `ppe_val.mp4` gerado a 5 fps — o vídeo era o teto
de FPS e mascarava o efeito. Fonte para teste de fluidez precisa ser ≥30 fps.

## 2. Fan / saúde térmica (item 7)

- **PWM 255 (100%) + tach RPM 0, perfil `quiet`**: verificação física do Vitor → **fan GIRA**.
  RPM 0 = fio de tach ausente no conector (landmine de plataforma: não usar RPM como health-check
  neste hardware; usar PWM + curva térmica).
- Após ~5 h de carga sustentada (mosaico 28 cams, GPU ~92%, ~16,6 W): temps 55–60 °C — folga grande
  até throttle (~95 °C+). Perfil `cool` + clocks travados: pendente do gate sudo (Vitor).

## 3. Telemetria robusta (item 8)

- Coletor task-100 (tegrastats 5 s) mantido intacto + **sampler de campanha** novo
  (`~/jetson-experiments/campaign/sampler.py`, 2 s): fan PWM/RPM, rails INA3221 (VDD_IN,
  VDD_CPU_GPU_CV, VDD_SOC em mW), gpu_load fino (sysfs), freqs GPU/CPU, temps completas e
  **`label` de fase/cenário** (`phase.label`) — JSONL `telemetry_campaign.jsonl`, join por ts.
- FPS/stream e drops: logs `PERF` do deepstream-app por cenário (`~/jetson-experiments/logs/camp_*.log`).
- Gap identificado no coletor 100 (para port futuro): fan, rails individuais, label arbitrário de fase.

## 4. Escala YOLOX até 40 + alavancas (itens 2+3)

### Alavanca batch dinâmico (trtexec, engine fp16 1..40, opt=28 — build 24 min)
- batch-1: 465 qps (single) / ~250 inf/s no pipeline DS batch-1
- **batch-28: 19,3 qps de batch = 539 inf/s (~2,2× o caminho batch-1)** · ~2 ms/imagem

### Matriz fp16 (modelo real PPE tiny, substream 480p@30fps, MediaMTX+pacer, perfil quiet, clocks dinâmicos)

| Cenário | batch | interval | tracker | FPS/stream | GPU | VDD_IN | Temp GPU máx |
|---|---|---|---|---|---|---|---|
| 28_base (config 102) | 1 | 0 | — | 8,97 | 64% | 16,7 W | 56,8 °C |
| 28_batch | 28 | 0 | NvDCF | 16,51 **(+84%)** | 98% | 23,1 W | 64,1 °C |
| **28_prod** | 28 | 5 | NvDCF | **21,78** | **64%** | **12,9 W** | 56,0 °C |
| 40_batch | 40 | 0 | NvDCF | 9,36 | 96% | 22,6 W | 64,0 °C |
| **40_prod** | 40 | 5 | NvDCF | **15,35** | 61% | 12,8 W | 55,6 °C |

- FPS uniforme entre streams (min=avg=max) e `errs=0` em todos — zero streams mortos com `ulimit` fix.
- **Achado:** nos cenários `prod` a GPU fica em ~64% mas o FPS não bate 30 → com mosaico na tela, o
  gargalo desloca para o caminho de RENDER (tiler/OSD/X11 a full rate em 28–40 tiles), não a inferência.
  **Produção RVB não renderiza mosaico** → capacidade honesta medida headless (fakesink) abaixo.

### Caçada ao gargalo dos cenários `prod` (iterações v2→v6)

Sintoma: `prod` capava em 15–22 FPS/stream com **GPU a só 25–57%** — algo serializava fora da GPU.
Eliminação sistemática (cada hipótese = 1 rodada de matriz):

| Iteração | Hipótese | Teste | Resultado |
|---|---|---|---|
| v2 | Render/X11 | headless (fakesink) | ≈ igual → **não era** |
| — | Fonte (pacer) | decode-only (gie off) | **31,6 FPS** ✓ fonte OK após shard do pacer (5 proc × 8 streams; single-proc saturava ~600 f/s agregado — landmine) |
| v3 | OSD | `[osd] enable=0` | igual → não era |
| v3 | Tamanho do tracker | 480×288 vs 960×544 | igual → não era |
| v3 | Tracker em si | int5 SEM tracker | +5 FPS a 40 → custo real do NvDCF ~800 upd/s |
| v4 | `batched-push-timeout` | 33 ms→8 ms→4 ms + novo mux | igual → não era |
| v5 | **Tiler (VIC) mesmo headless** | `[tiled-display] enable=0` | **+4 FPS** (40: 15→19; 28: 20→24) — tiler compõe mesmo com fakesink |
| v6 | **Stall de latência do nvinfer** (batch-40 = 76 ms a cada 200 ms → backpressure → drops em live) | sub-batch nvinfer 8/16 | *(em execução)* |

Evidência do backpressure: `VideoErrorInfo_OutputBufferUnavailable` no decoder durante os stalls.
Engine em batch-40: 13,7 qps = **549 inf/s**, 75,7 ms/batch (trtexec) — a inferência em si tem folga.

| v6 | **Stall de latência do nvinfer** (batch-40 = 76 ms bloqueia a cada 200 ms → drops em live) | **sub-batch nvinfer 8/16** (menor que o batch do mux) | **+4 FPS** — CONFIRMADO: 40: 19→23,1 · 28: 24→**28,4** |

### ✅ CONFIG ÓTIMA (fp16, perfil quiet, clocks dinâmicos — sem sudo ainda)

| | **28 cams (produção RVB)** | **40 cams (expansão)** |
|---|---|---|
| nvinfer | batch dinâmico, **sub-batch 8**, `interval=4` | sub-batch 16, `interval=3` |
| tracker | NvDCF perf (960×544) | NvDCF perf |
| pipeline | headless: sem tiler, sem OSD | idem |
| **FPS/stream** | **29,0 (taxa cheia)** | 22,4 |
| **Cadência de inferência** | **5,8 inf/s/cam ✓ alvo 5** | **5,6 inf/s/cam ✓** |
| GPU / VDD_IN / temp GPU | 42% · 15,2 W · 57,4 °C | 65% · 18,7 W · 59,0 °C |
| Streams mortos / erros | 0 / 0 | 0 / 0 |

- **Limite seguro: 40 câmeras SIM no alvo de 5 inf/s/cam**, com GPU 65% e ~20 W (modo 40W) — margem
  térmica confortável (59 °C vs throttle ~95 °C+) mesmo em perfil de fan `quiet`.
- 28 câmeras rodam FOLGADAS (GPU 42%) — headroom para modelo mais pesado (item 9) ou Recognition.
- `interval=2` a 40 cams piora (20,5 FPS, GPU 80%): sobre-amostrar derruba a entrega. O ponto ótimo
  é o menor interval que ainda sustenta a taxa da fonte.
- Ganho por alavanca (40 cams, headless): fluidez/interval+tracker é a base; **tiler OFF +4 FPS**;
  **sub-batch nvinfer +4 FPS**; batch dinâmico habilita tudo (engine 549 inf/s @b40); mux timeout
  e OSD ~neutros; tracker custa ~1,5–5 FPS conforme N.

## 5. RF-DETR (item 4 / task-105)

### Pesquisa (referências no final)
- Variantes Apache: **Nano/Small/Medium/Large** (30–34M params; XL/2XL são PML 1.0 — **proibidas** no caminho servido).
- Treino: pacote `rfdetr` 1.8.3, API `RFDETRNano().train(dataset_dir=<COCO roboflow>, epochs, batch_size, grad_accum_steps)`; T4 16GB → `batch 4 × accum 4`.
- Export: `model.export()` → ONNX `dets [B,Q,4]` (cxcywh normalizado) + `labels [B,Q,C]` (logits), **sem NMS** → nvinfer `cluster-mode=4`; preproc **ImageNet RGB** (`net-scale-factor=0.01735`, `offsets=123.675;116.28;103.53`).
- **Parser DeepStream PRÓPRIO escrito** (`~/jetson-experiments/rfdetr-parser/nvdsparsebbox_rfdetr.cpp`,
  `NvDsInferParseCustomRFDETR`): sigmoid(melhor logit) + threshold, denormaliza cxcywh, sem NMS. Compilado ok.
- DLA: literatura + fórum NVIDIA confirmam **transformer não roda em DLA** (attention/LayerNorm/GELU
  não suportados → fallback massivo). Caracterização no nosso box abaixo.
- Benchmark no NOSSO hardware (infracv/rf-detr-cpp, Orin NX 16GB, TRT 10.3): **Nano fp16 = 120 FPS / 8,3 ms** batch-1.
- INT8 em DETR não compensa: +5–10% de velocidade, mAP pode cair ~20% (fontes no rodapé).

### Treino no box (comparável à task-101)

| | YOLOX-Tiny (101) | **RF-DETR Nano** |
|---|---|---|
| Dataset / épocas | SiaBar PPE COCO / 10 | idem / 10 |
| Batch | 16 | 4 × grad_accum 4 (efetivo 16) |
| **Wall-clock** | **8m09s** (~73 ép/h) | **52m15s** (~11,5 ép/h) — **6,4× mais lento** |
| **mAP@0.5:0.95 (val)** | 71,2 | **75,6 (+4,4 pts)** |
| Potência/GPU no treino | ~6,3 W · 2,4 GB | ~18 W · GPU 83% |

- Extras `rfdetr[train,loggers]` instalaram sem clobber do torch Jetson (check pós-install ✓).
- Treino DE EXPERIMENTO no box (produção treina off-box, task-086) — mas o número comparável existe.

### Export/engine/DLA/stress

- **Export** (`model.export()`): contrato confirmado no Netron-por-script — `dets [1,300,4]` +
  `labels [1,300,10]`, input `384×384`, batch-1 estático.
- **Engine fp16: 142 qps / 7,14 ms** (batch-1, trtexec) — acima da referência pública de 120 FPS
  no mesmo hardware (infracv/rf-detr-cpp).
- **DLA: 2.303 camadas caem para GPU** (vs 113 do YOLOX) — fallback ~20× pior; **RF-DETR em DLA é
  inviável**, como previsto pela literatura. GPU-only definitivo para transformer.
- **Parser próprio validado em campo**: sanidade visual 4 tiles (vídeo PPE, tela física) →
  **2.284 detecções / 600 frames com classes corretas** (Boots 872 · Vest 716 · Helmet 368 ·
  Person 328), zero classes-lixo. `NvDsInferParseCustomRFDETR` + preproc ImageNet RGB +
  `cluster-mode=4` (screenshot `rfdetr_sanity.png`).
- Teto teórico batch-1: 142 inf/s → 28 cams × 5 = 140 (justo) · 40 × 5 = 200 (**não fecha**;
  export batch-dinâmico do RF-DETR fica como melhoria futura).

### Stress RF-DETR (mesma infra/config ótima do YOLOX)

| Cenário | FPS/stream | Cadência inf/s/cam | GPU | VDD_IN | Obs |
|---|---|---|---|---|---|
| batch-1, 28 cams, int4 | 15,4 | 3,1 | 67% | 17,7 W | abaixo do alvo 5 |
| batch-1, 40 cams, int3 | 9,5 | 2,4 | 68% | 19,4 W | abaixo |
| batch-1, 28 cams, int0 | 4,4 | 4,4 | 94% | 21,1 W | engine saturada |
| **batch-8 dyn, 28 cams, int4** | 16,9 | **3,4** | 81% | 20,2 W | melhor config RF-DETR |
| batch-8 dyn, 40 cams, int3 | 9,4 (min 0!) | 2,3 | 99% | 19,9 W | **streams morrem — inviável** |

- Engine batch-8: 21,5 qps = **172 inf/s** (+21% vs batch-1) — batching em transformer escala bem
  menos que em CNN (YOLOX: +115%).
- **Veredito RF-DETR Nano neste box: ~20 câmeras a 5 inf/s/cam, ou 28 câmeras a ~3,4 inf/s/cam.**
  40 câmeras não fecham em nenhuma config (200 inf/s > 172 de teto).

### Bench head-to-head (dataset PPE, 10 épocas, mesmo box)

| Métrica | YOLOX-Tiny | RF-DETR Nano |
|---|---|---|
| Treino (10 ép) | **8m09s** | 52m15s (6,4×) |
| mAP@0.5:0.95 | 71,2 | **75,6 (+4,4)** |
| Engine fp16 batch-1 | 398 qps (2,6 ms) | 142 qps (7,1 ms) |
| Teto batched | **549 inf/s** (b28) | 172 inf/s (b8) |
| 28 cams (config ótima) | **29 FPS · 5,8 inf/s/cam · GPU 42%** | 16,9 FPS · 3,4 inf/s/cam · GPU 81% |
| 40 cams | **22,4 FPS · 5,6 inf/s/cam · GPU 65%** | inviável (streams morrem) |
| DLA | 113 fallbacks (GPU-only decidido) | **2.303 fallbacks (impossível)** |
| INT8 | viável (calibração real) | não compensa (literatura: −mAP grande) |

### Recomendação (RVB e além)

- **Produção 28–40 câmeras: YOLOX** (Tiny provou o pipeline; S em teste como candidato de acurácia).
  Só o YOLOX sustenta o alvo de 5 inf/s/cam nas 28–40 câmeras, com folga térmica e opção futura de DLA.
- **RF-DETR Nano = detector de ACURÁCIA para sites ≤20 câmeras** ou câmeras selecionadas
  (ex.: zonas críticas com cadência 3–4 inf/s), +4,4 mAP sobre o Tiny.
- Híbrido possível por câmera (nvinfer por grupo de sources) — fora do escopo desta campanha.

## 6. Cena de alta densidade — carros (item 5)

- **Landmine no caminho**: o checkpoint YOLOX-Nano 0.1.1rc0 (2021) usado como "modelo leve" produz
  **zero detecções** com preproc correto (objectness colapsado — confirmado por KITTI 100% vazio em
  6489 frames; ontem os "1443 arquivos" nunca tiveram conteúdo verificado). Detector para a cena de
  carros trocado para o **TrafficCamNet do próprio DeepStream** (`resnet18_trafficcamnet_pruned.onnx`),
  que é o detector canônico de tráfego do sample.
- Setup: 9 tiles (3×3) do `sample_1080p_h264.mp4` 1080p30, batch 9 fp16, na tela física.
  A = `interval=0` sem tracker (pior caso: máximo de inferências) · B = `interval=4` + NvDCF.

**Resultados** (engine b9 fp16 cacheada em `~/jetson-experiments/tcn/`):

| Variante | FPS/stream | GPU | VDD_IN | Observação |
|---|---|---|---|---|
| A — `interval=0` (todo frame) | 29,7 | alto | **~22,4 W inst** | pico de carga; boxes re-detectadas a cada frame |
| B — `interval=4` + NvDCF | 30,0 | 18% | **6,9 W** | mesma fluidez visual, IDs estáveis, **3× menos energia** |

- **Densidade real: 261.684 detecções em 12.987 frames (~20 boxes/frame)** — 188,7k `car`,
  66,3k `person`, 6,6k `bicycle` (KITTI dump verificado com conteúdo, não só contagem de arquivos).
- Na cena densa o tracker+interval não degrada a qualidade visual das boxes (gravações
  `dens3_rec_A/B.mp4`); em A as boxes "vibram" por re-detecção, em B seguem suaves com ID.
- Aprendizado de método: **contar arquivos KITTI não basta — verificar conteúdo** (o nano-2021
  gerava milhares de arquivos VAZIOS).

## 7. Impacto de rede + Recognition (item 6) — PARCIAL

- **Câmera real Intelbras: fora desta campanha por decisão do Vitor** (sem creds) — registrado como
  pendência; o passo mede jitter RTSP/banda/reconexão reais vs sintético.
- **Overhead do Recognition (simulado local):** cenário ótimo de 28 cams rodando junto com um
  simulador do sync-agent (28 eventos de detecção/s ~2 KB + clipe de evidência 5 MB a cada 30 s,
  HTTP localhost):

| | FPS/stream | GPU | VDD_IN |
|---|---|---|---|
| 28 cams referência | 29,62 | 69% | 15,1 W |
| 28 cams + carga Recognition | 30,01 | 59% | 15,1 W |

  → **Impacto no pipeline: zero (dentro do ruído).** O custo do envio de eventos/evidência é
  desprezível frente à folga de CPU (8 cores, pipeline usa ~40%). Limitação honesta: HTTP local
  não exercita WAN/WireGuard — o teste com câmera real + túnel fica pendente das creds.

## 8. Modelos pesados + INT8 (item 9)

### YOLOX-S (candidato de acurácia CNN, 640×640)

- Treino: **14m17s / 10 épocas** (vs 8m09s do Tiny) · **AP 72,31** (+1,1 sobre o Tiny).
- No NOSSO dataset (1126 imgs, 10 épocas), o S não paga o custo: ganho marginal de acurácia por
  ~4× o custo de inferência (640 vs 416). Com dataset RVB real/mais épocas o gap pode abrir —
  reavaliar no treino de produção (task-086). Stress do S não executado por decisão (curva já
  respondida pelos extremos Tiny/RF-DETR).

### INT8 com calibração REAL (300 imgs do train set, entropy, TRT PTQ) — 🏆 CONFIG VENCEDORA

| Cenário (YOLOX-Tiny INT8, config ótima) | FPS/stream | Cadência | GPU | VDD_IN | Temp |
|---|---|---|---|---|---|
| **28 cams, int4, sub-batch 8** | **31,5 (taxa cheia)** | **6,3 inf/s/cam** | **47%** | 13,9 W | 53,1 °C |
| **40 cams, int3, sub-batch 8** | **24,9** | **6,2 inf/s/cam** | **45%** | 16,2 W | 56,7 °C |

- vs fp16 a 40 cams: **+11% de entrega (22,4→24,9) com −20 pontos de GPU (65→45%)** — INT8 devolve
  headroom enorme para o Recognition/modelo maior/mais câmeras.
- Engine 7 MB (fp16 tinha 13,4 MB). Build INT8 exige `parser.parse_from_file` (pesos externos).
- **Pendência honesta:** mAP do engine INT8 não foi validado contra o fp16 (PTQ bem calibrado
  tipicamente perde ~1 pt em CNN; validar no eval do modelo de produção).

### Curva acurácia × custo (dataset PPE, este box)

| Modelo | mAP | Teto inf/s | 40 cams @5 inf/s? |
|---|---|---|---|
| YOLOX-Tiny fp16 | 71,2 | 549 | ✓ (GPU 65%) |
| **YOLOX-Tiny INT8** | ~71 (validar) | >600 | **✓ (GPU 45%)** |
| YOLOX-S fp16 | 72,3 | ~est. 140–180 | limítrofe |
| RF-DETR Nano fp16 | **75,6** | 172 | ✗ (~20 cams @5) |

## 9. Limpeza pré-RVB (DIFERIDA — registrada, NÃO executada)

Candidatos a remoção ao fim da campanha (hoje ~27 GB usados de 116 GB):
- `~/jetson-experiments/train-venv` (~6 GB) — recriável pelo REGRAS
- `~/jetson-experiments/dataset/ppe-coco` (102 MB) + `~/deepstream_v7.1/*.tbz2/deb/whl` x86 (~10 GB inúteis no box!)
- Engines/onnx de teste (nano fp32/int8/dla, dyn), logs de stress, `kitti_out/`, gravações/screenshots já copiadas
- Manter: parser 088 + rfdetr-parser, mediamtx, telemetria, engines finais de produção

---

# ANEXO — Relatório detalhado (metodologia, números crus, artefatos)

## A. Ambiente (verificado no box, C-04)

| Item | Valor |
|---|---|
| Hardware | Jetson Orin NX Super 16GB (Palit Pandora) · NVMe 116 GB · monitor HDMI 1920×1080 em `:1` |
| Stack | JetPack 6.2.1 / L4T r36.4.3 · CUDA 12.6 · TensorRT 10.3.0.30 · DeepStream 7.1 · driver 540.4.0 |
| Power | nvpmodel **40W** · perfil fan `quiet` · clocks dinâmicos (jetson_clocks NÃO aplicado — sudo pendente) |
| Treino | venv `train-venv`: torch 2.11.0+cu126 sm_87 (jetson-ai-lab.io jp6) · rfdetr 1.8.3 (+train,loggers) · YOLOX master Apache |
| Infra síntese | MediaMTX v1.19.2 arm64 · `pacer_shard.py` (UDP MPEG-TS, 8 streams/proc, burst 4) |
| Fontes | substream: `sample_480p.ts` (704×480@30, ~1,1 Mbps) · main: `sample_1080p.ts` (~5,8 Mbps) — loop |
| Telemetria | coletor task-100 (tegrastats 5 s) + `campaign/sampler.py` (2 s: fan PWM/RPM, INA3221 mW, gpu_load, freqs, temps, label) |
| Métrica FPS | `enable-perf-measurement` do deepstream-app (última linha PERF por cenário, avg/min/max entre streams) |

## B. Metodologia

1. Cada cenário roda 90–120 s com label próprio na telemetria (`phase.label`) e log dedicado (`logs/camp_<nome>.log`).
2. `run_scenario.sh`: mata pacers/stress → sobe N pacers shardados → espera paths ready no MediaMTX → sobe deepstream-app (`ulimit -n 65535`) → extrai PERF + média de 10 amostras de telemetria do label → screenshot.
3. Cadência de inferência = FPS_entregue / (interval+1). Alvo de produção: **5 inf/s/câmera**.
4. Validação de detecção = conteúdo do KITTI dump (não contagem de arquivos — landmine nano-2021).
5. Fontes de erro controladas: fonte validada por decode-only (31,6 FPS), erros contados por cenário, fps_min≈fps_avg como critério de uniformidade (nenhum stream morto, exceto onde anotado).

## C. Matriz completa de cenários (números crus)

### YOLOX-Tiny fp16 (engine dinâmica 1..40, opt 28 — build 24 min · 549 inf/s @b28 · 75,7 ms/batch @b40)

| # | Cenário | N | batch | int | trk | tiler | OSD | sink | FPS/stream | GPU | VDD_IN | T_gpu | errs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1 | 28_base | 28 | 1 | 0 | – | on | on | tela | 8,97 | 64% | 16,7 W | 56,8° | 0 |
| v1 | 28_batch | 28 | 28 | 0 | ✓ | on | on | tela | 16,51 | 98% | 23,1 W | 64,1° | 0 |
| v1 | 28_prod | 28 | 28 | 5 | ✓ | on | on | tela | 21,78 | 64% | 12,9 W | 56,0° | 0 |
| v1 | 40_batch | 40 | 40 | 0 | ✓ | on | on | tela | 9,36 | 96% | 22,6 W | 64,0° | 0 |
| v1 | 40_prod | 40 | 40 | 5 | ✓ | on | on | tela | 15,35 | 61% | 12,8 W | 55,6° | 0 |
| v2 | 28_prod_hl | 28 | 28 | 5 | ✓ | on | on | fake | 20,23 | 46% | 11,3 W | 51,8° | 0 |
| v2 | 40_prod_hl | 40 | 40 | 5 | ✓ | on | on | fake | 15,22 | 29% | 11,8 W | 52,3° | 0 |
| — | raw40 (decode-only) | 40 | – | – | – | on | on | fake | **31,62** | – | – | – | 0 |
| v3 | 28_prod_noosd | 28 | 28 | 5 | ✓ | on | off | fake | 20,15 | 35% | 10,8 W | 50,7° | 0 |
| v3 | 40_prod_noosd | 40 | 40 | 5 | ✓ | on | off | fake | 15,40 | 31% | 11,8 W | 52,2° | 0 |
| v3 | 40_prod_smalltrk (480×288) | 40 | 40 | 5 | ✓ | on | off | fake | 14,85 | 34% | 11,9 W | 52,8° | 0 |
| v3 | 40_batch_retry | 40 | 40 | 0 | ✓ | on | off | fake | 10,58 | 99% | 24,2 W | 64,3° | 0 |
| v3 | 40_int5_notrk | 40 | 40 | 5 | – | on | off | fake | 20,09 | 49% | 11,9 W | 56,2° | 0 |
| v4 | 40_mux8ms | 40 | 40 | 5 | ✓ | on | off | fake | 14,99 | 25% | 11,4 W | 52,4° | 0 |
| v4 | 40_mux4ms | 40 | 40 | 5 | ✓ | on | off | fake | 15,59 | 37% | 11,5 W | 53,0° | 0 |
| v4 | 40_newmux | 40 | 40 | 5 | ✓ | on | off | fake | 15,23 | 36% | 11,5 W | 53,2° | 0 |
| v5 | 40_notiler | 40 | 40 | 5 | ✓ | **off** | off | fake | 19,04 | 35% | 12,5 W | 53,3° | 0 |
| v5 | 28_notiler | 28 | 28 | 5 | ✓ | off | off | fake | 24,03 | 44% | 12,5 W | 53,3° | 0 |
| v5 | 40_notiler_notrk | 40 | 40 | 5 | – | off | off | fake | 20,53 | 15% | 6,4 W | 50,4° | 3* |
| v6 | 40_ib8 (sub-batch 8) | 40 | **8** | 5 | ✓ | off | off | fake | 22,82 | 38% | 14,8 W | 54,5° | 0 |
| v6 | 40_ib16 | 40 | **16** | 5 | ✓ | off | off | fake | 23,11 | 35% | 14,7 W | 55,7° | 0 |
| v6 | 28_ib8 | 28 | 8 | 5 | ✓ | off | off | fake | 28,42 | 68% | 14,2 W | 55,7° | 0 |
| v7 | 40_int3 | 40 | 16 | **3** | ✓ | off | off | fake | 22,43 | 65% | 18,7 W | 59,0° | 0 |
| v7 | **28_int4 (ótima fp16)** | 28 | 8 | **4** | ✓ | off | off | fake | **29,04** | 42% | 15,2 W | 57,4° | 0 |
| v7 | 40_int2 | 40 | 16 | 2 | ✓ | off | off | fake | 20,50 | 80% | 20,3 W | 61,9° | 0 |
| ov | 28_ref | 28 | 8 | 4 | ✓ | off | off | fake | 29,62 | 69% | 15,1 W | 55,6° | 0 |
| ov | 28_comrec (+ sim Recognition) | 28 | 8 | 4 | ✓ | off | off | fake | 30,01 | 59% | 15,1 W | 56,7° | 0 |

\* erros transitórios de largada (`OutputBufferUnavailable`) — evidência do backpressure do nvinfer.

### YOLOX-Tiny INT8 (calibração entropy real, 300 imgs train, engine 7 MB)

| Cenário | N | batch | int | FPS/stream | Cadência | GPU | VDD_IN | T_gpu | errs |
|---|---|---|---|---|---|---|---|---|---|
| **int8_28_prod** | 28 | 8 | 4 | **31,52** | **6,3** | 47% | 13,9 W | 53,1° | 0 |
| **int8_40_prod** | 40 | 8 | 3 | **24,87** | **6,2** | 45% | 16,2 W | 56,7° | 0 |

### RF-DETR Nano (384×384; engine b1 142 qps/7,1 ms · b8 21,5 qps = 172 inf/s/46,8 ms)

| Cenário | N | batch | int | FPS/stream | Cadência | GPU | VDD_IN | T_gpu | obs |
|---|---|---|---|---|---|---|---|---|---|
| rf_28_prod | 28 | 1 | 4 | 15,41 | 3,1 | 67% | 17,7 W | 58,3° | |
| rf_40_prod | 40 | 1 | 3 | 9,49 | 2,4 | 68% | 19,4 W | 61,6° | |
| rf_28_full | 28 | 1 | 0 | 4,41 | 4,4 | 94% | 21,1 W | 64,6° | engine saturada |
| rfb8_28_prod | 28 | 8dyn | 4 | 16,85 | 3,4 | 81% | 20,2 W | 61,1° | melhor RF-DETR |
| rfb8_40_prod | 40 | 8dyn | 3 | 9,36 (min 0!) | 2,3 | 99% | 19,9 W | 59,9° | **stream morto** |

### Fluidez e densidade (tela física, 1080p30)

| Teste | Config | FPS | GPU | VDD_IN |
|---|---|---|---|---|
| Fluidez A (4 tiles, nano) | int0, sem trk | 30 | 57,8% | 9,67 W |
| Fluidez B | int4 + NvDCF | 30 | 37,3% | 7,46 W |
| Densidade A (9 tiles, TrafficCamNet) | int0, sem trk | 29,71 | alto | ~22,4 W |
| Densidade B | int4 + NvDCF | 30,01 | 18% | 6,9 W |

Densidade: 261.684 detecções / 12.987 frames (car 188.739 · person 66.294 · bicycle 6.624 · road_sign 27).

### Treinos (mesmo dataset SiaBar PPE COCO: 1126 train / 326 valid, 10 épocas)

| Modelo | Res | Batch | Wall-clock | mAP@0.5:0.95 | Potência |
|---|---|---|---|---|---|
| YOLOX-Tiny | 416 | 16 | 8m09s | 71,2 | ~6,3 W |
| YOLOX-S | 640 | 8 | 14m17s | 72,31 | — |
| RF-DETR Nano | 384 | 4×accum4 | 52m15s | **75,63** | ~18 W · GPU 83% |

## D. Inventário de artefatos no box (`~/jetson-experiments/`)

- **Engines**: `ppe_yolox_tiny_fp16.engine` (b1) · `ppe_tiny_dyn_fp16.engine` (b1..40) · `ppe_tiny_dyn_int8.engine` 🏆 · `rfdetr_nano_fp16.engine` (b1) · `rfdetr_nano_b8_fp16.engine` · `tcn/…_b9_gpu0_fp16.engine`
- **Modelos/ckpts**: `YOLOX/YOLOX_outputs/{ppe_yolox_tiny,ppe_yolox_s}/` · `rfdetr_out/checkpoint_best_ema.pth` + `export/`, `export_b8/`
- **Parsers**: `~/yolox-deepstream-parser/libnvdsparsebbox_yolox.so` (088) · `rfdetr-parser/libnvdsparsebbox_rfdetr.so` (próprio, 105)
- **Infra**: `mediamtx` + `stress102/{gen_campaign.sh,pacer_shard.py,configs}` · `campaign/{run_scenario.sh,sampler.py,matrizes}`
- **Dados**: `campaign/telemetry_campaign.jsonl` (toda a campanha, etiquetada) · `logs/camp_*.log` (PERF por cenário) · `artifacts/` (screenshots + gravações)
- **Configs ótimas**: `stress102/config_infer_ppe_int8b8.txt` (28/40 prod) · `config_infer_rfdetr_b8.txt` · tracker `NvDCF_perf`

## E. Cronologia da campanha (2026-07-16 22h → 07-17 02h30, ~4h30)

setup/telemetria/fan → fluidez A/B → engine dinâmica (24 min build) → matrizes v1–v7 (caçada de gargalo) → headless/overhead → densidade (3 tentativas: nano-2021 dud → TCN engine cache) → RF-DETR (treino 52 min → export → parser → DLA → stress b1/b8) → YOLOX-S (14 min) → INT8 (build+cenários) → relatório/painel final.

## Referências

**RF-DETR (pesquisa 2026-07-17):**
- Repo oficial + variantes/licenças: github.com/roboflow/rf-detr (Nano–Large Apache-2.0; XL/2XL PML 1.0 — proibidas) · blog.roboflow.com/rf-detr-nano-small-medium
- Treino/params: rfdetr.roboflow.com/latest/learn/train · blog.roboflow.com/train-rf-detr-on-a-custom-dataset (T4 16GB: batch 4 × accum 4)
- Export/formato de saída: rfdetr.roboflow.com/latest/learn/export · deepwiki.com/roboflow/rf-detr/4.1-onnx-export · issues #473/#489 (dets cxcywh norm + labels logits; sigmoid+topK oficial)
- DeepStream: github.com/ridgerun-ai/deepstream-rfdetr (parser de referência; escrevemos o nosso próprio) · deepstream_tao_apps (parsers DDETR/DINO da NVIDIA) · fórum NVIDIA t/353198 (Orin+DS7.1+RF-DETR)
- Benchmarks: github.com/infracv/rf-detr-cpp (**Orin NX 16GB: Nano fp16 120 FPS** — nós medimos 142) · RidgeRun AGX Orin DS: Nano 238 fp16
- DLA/transformers: proventusnova.com/blog/tensorrt-vs-dla-jetson-orin · fórum NVIDIA t/286851 (confirmado no box: 2.303 fallbacks)
- INT8 em DETR: issue #955 (+5-10% apenas) · benchmark Condados/Medium (−21% mAP) — não usamos
- Paper: arxiv.org/abs/2511.09554 (RF-DETR NAS, ICLR 2026) · arxiv 2504.13099 (DETR vs YOLO em oclusão)

**DeepStream/Jetson (aplicados na campanha):**
- NvDCF tracker: configs `config_tracker_NvDCF_*.yml` do DS 7.1 (sample é a referência de fluidez)
- nvinfer `interval`/batch/sub-batch: DS docs Gst-nvinfer; achado do stall de latência é empírico nosso
- nvstreammux batched-push-timeout / new mux: DS docs (testado: neutro no nosso caso)
- TrafficCamNet (densidade): modelo `Primary_Detector` do DS 7.1

## Limpeza pré-RVB (atualizada — DIFERIDA)

Adicionar aos candidatos: `rfdetr_out/` (ckpts ~1,5 GB + exports 119 MB), engines rfdetr b1/b8,
`ppe_tiny_dyn_int8.engine` + calib cache, `tcn/` (engine+onnx), gravações `*_rec_*.mp4` já copiadas,
`YOLOX_outputs/ppe_yolox_s`, wheels/caches pip do train-venv (~10 GB total estimado a liberar).
Manter: parsers (088 + rfdetr), configs ótimas, mediamtx+pacer_shard, telemetria, JSONLs da campanha.
