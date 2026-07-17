# Campanha de escala e otimização — Jetson Orin NX (tasks 105 + 106) — 2026-07-17

> Objetivo: limite SEGURO do hardware com o MODELO REAL até 40 câmeras, config ótima, fluidez das
> bounding boxes, bench YOLOX × RF-DETR, impacto de rede/Recognition.
> 28 câmeras = produção (RVB) · 40 = expansão (upsell). Execução no box real via SSH, tela física `:1`.
> Baseline: `EXPERIMENTOS_2026-07-16.md` (103/104/101/102).

## Sumário executivo (preenchido ao final)

*(em construção)*

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

### Treino/export/stress no box
*(em execução)*

## 6. Cena de alta densidade — carros (item 5)

*(em execução)*

## 7. Impacto de rede + Recognition (item 6) — PARCIAL

- **Câmera real Intelbras: fora desta campanha por decisão do Vitor** (sem creds) — registrado como
  pendência; o passo mede jitter RTSP/banda/reconexão reais vs sintético.
- Overhead do Recognition (sync-agent/WireGuard/evidência): medição sintética abaixo.

## 8. Modelos pesados (item 9)

*(em execução)*

## 9. Limpeza pré-RVB (DIFERIDA — registrada, NÃO executada)

Candidatos a remoção ao fim da campanha (hoje ~27 GB usados de 116 GB):
- `~/jetson-experiments/train-venv` (~6 GB) — recriável pelo REGRAS
- `~/jetson-experiments/dataset/ppe-coco` (102 MB) + `~/deepstream_v7.1/*.tbz2/deb/whl` x86 (~10 GB inúteis no box!)
- Engines/onnx de teste (nano fp32/int8/dla, dyn), logs de stress, `kitti_out/`, gravações/screenshots já copiadas
- Manter: parser 088 + rfdetr-parser, mediamtx, telemetria, engines finais de produção

## Referências

*(lista completa ao final — pesquisa RF-DETR com URLs no anexo da task)*
