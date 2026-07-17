# Cenário RVB multi-módulo — 1 Jetson, 28 câmeras, 3 módulos JUNTOS (tasks 107–112) — 2026-07-17

> ADR-0053. Objetivo: preparar modelos por grupo, medir o CUSTO REAL dos 3 módulos simultâneos
> (Qualidade + Estacionamento + EPI) no Orin NX, com as 2 câmeras 4MP da Qualidade em alta-res POR
> ROI (ponto crítico nunca medido), esqueleto monofatura, exploração de modelos na trava de licença
> e dashboard integrado. Base: config ótima da campanha (CAMPANHA_ESCALA_2026-07-17.md).
> Execução no box real (`pandora`), tela física `:1`. **(EM EXECUÇÃO — seções preenchidas conforme medido)**

## Layout de câmeras do cenário (28 streams sintéticos, MediaMTX+pacer)

| Grupo | Paths | Fonte | Modelo | Config |
|---|---|---|---|---|
| EPI (16×2MP) | cam0–15 | substream 704×480@30 | YOLOX-Tiny PPE **INT8** | int4, sub-batch 8, NvDCF, headless |
| Estacionamento (8×2MP) | cam16–23 | substream 704×480@30 | YOLOX-Tiny **COCO** fp16 (pessoa/veículo) | int4, sub-batch 8, NvDCF, classes 0/2/3/5/7 |
| Qualidade aux (2×2MP) | cam24–25 | substream 704×480@30 | YOLOX-Tiny PPE INT8 + NvDCF | int2 (cronômetro de etapa) |
| Qualidade principal (2×4MP) | cam26–27 | **2560×1440@30** (gerada NVENC) | RF-DETR Nano 384 | **alta-res POR ROI**: nvdspreprocess, 4 ROIs 640×640/câmera, tensor-from-meta, batch 8 |

- Instâncias nvinfer separadas por grupo = 4 processos deepstream-app (mesma GPU), roteando cada
  grupo pro seu modelo — espelha `active_module`+`model_<módulo>_id` (task-045) no edge.
- Telemetria: sampler da campanha (2 s, JSONL) + label `mm_<cenário>` por fase + **ram_used_mb novo**;
  FPS/drops POR MÓDULO dos logs PERF de cada instância.

## 1. Modelos por grupo (task-107)

| Grupo | Modelo | Licença | Engine | Status |
|---|---|---|---|---|
| EPI | YOLOX-Tiny PPE INT8 (campanha) | Apache-2.0 | `ppe_tiny_dyn_int8.engine` | reuso ✓ |
| Estacionamento | YOLOX-Tiny COCO 0.1.1rc0 oficial Megvii | Apache-2.0 (código+pesos) | `mm/yolox_tiny_coco_dyn_fp16.engine` (dyn 1..16) | _build/validação abaixo_ |
| Qualidade aux | YOLOX-Tiny PPE INT8 + NvDCF | Apache-2.0 | reuso | ✓ |
| Qualidade principal | RF-DETR Nano PPE (384) por ROI | Apache-2.0 | `rfdetr_nano_b8_fp16.engine` + nvdspreprocess | _sanidade abaixo_ |

### Juiz mAP_small (Qualidade principal) — métricas reais (val PPE, 10 épocas)

| Modelo | mAP@0.5:0.95 | **mAP_small** | mAP_medium | mAP_large |
|---|---|---|---|---|
| YOLOX-Tiny | 0.712 | 0.385 | 0.504 | 0.742 |
| YOLOX-S | 0.723 | 0.521 | 0.500 | 0.751 |
| **RF-DETR Nano** | **0.754** | **0.565** | 0.549 | 0.803 |

- RF-DETR Nano: COCOeval rodado no box (best_ema, 326 imgs val — `train_metrics/rfdetr-nano-ppe.sizes.json`).
- **Veredito do juiz mAP_small: RF-DETR Nano vence** (0.565 > 0.521 do S > 0.385 do Tiny) —
  a escolha RF-DETR por ROI pra Qualidade principal está validada nas duas pontas (acurácia
  em objeto pequeno E custo: GPU 20% com drop=5).
- **Achado secundário:** YOLOX-S ganha do Tiny em small por +13,6 pts (0.521 vs 0.385) — se a
  Qualidade precisar de CNN (ex.: DLA futuro), o S é o candidato, não o Tiny.

## 2. Métricas de treino persistidas (item 3)

- Extrator `mm/extract_train_metrics.py` → JSONL por modelo em `mm/train_metrics/` (copiado para
  `docs/edge/train_metrics/`): época, ap5095/ap50, ap_small/medium/large, losses, LR
  (YOLOX: train_log COCOeval; RF-DETR: metrics.csv Lightning + per-class AP + F1/precision/recall).
- Base de dados do dashboard task-112.

## 3. Stress 3 módulos juntos (task-111) — RESULTADOS

Infra: 4 instâncias `deepstream-app` simultâneas (uma por grupo), MediaMTX + pacer shardado
(26×480p30 + 2×2560×1440@30 gerada NVENC), headless (tiler/OSD off, fakesink), telemetria
sampler 2 s com label `mm_<cenário>` (+ `ram_used_mb` novo), FPS por módulo dos logs PERF.
Runner: `mm/run_mm.sh` · gerador `mm/gen_mm_app.sh` (sources RTSP explícitos por faixa).

### Isolados (baseline por grupo, 90 s cada)

| Grupo | Config | FPS/stream | Cadência inf | GPU | VDD_IN | T_gpu | errs |
|---|---|---|---|---|---|---|---|
| EPI 16 cams | Tiny INT8, int4, NvDCF | 30,8 | 6,2 inf/s/cam | 28% | 9,0 W | 53,0° | 0 |
| Estacionamento 8 | Tiny COCO fp16, int4, NvDCF | 31,0 | 6,2 inf/s/cam | 45% | 7,8 W | 51,3° | 0 |
| Qualidade aux 2 | Tiny INT8, int2, NvDCF | 30,5 | 10,2 inf/s/cam | 27% | 6,1 W | 49,1° | 0 |
| **Qualidade main 2×4MP ROI** | RF-DETR Nano, 4 ROIs 640² → 384, **drop-frame-interval=5** | 6,3 (pós-drop) | **6,3 inf/s/ROI** (25/cam) | **20%** | **10,3 W** | 58,3° | 0 |
| Qualidade main SEM cadência | idem, full-rate 30 fps | 23,5 (saturado) | ~118 inf/s total | **99%** | 27,5 W | 73,7° | 0 |

**O ponto crítico (custo do 4MP em alta-res por ROI) medido:** com cadência de produção
(drop=5 → 6,3 inf/s por ROI, acima do alvo 5), as 2×4MP custam **20% de GPU e ~10 W**.
Sem controle de cadência o caminho ROI **satura a engine RF-DETR sozinho** (ver landmine
do `interval` abaixo).

### Combinado — 3 módulos JUNTOS (28 câmeras, config produção, 120 s)

| Módulo | FPS/stream | Cadência | errs |
|---|---|---|---|
| EPI (16) | **31,9 (taxa cheia)** | 6,4 inf/s/cam | 0 |
| Estacionamento (8) | **30,9 (taxa cheia)** | 6,2 inf/s/cam | 0 |
| Qualidade aux (2) | **31,9** | 10,6 inf/s/cam | 0 |
| Qualidade main (2×4MP ROI) | 5,76 pós-drop | 5,8 inf/s/ROI | 0 |
| **Total box** | — | **~210 inf/s agregado** | **GPU 72% · 19,9 W · 64,0° · RAM 8,0 GB** |

✅ **O cenário RVB multi-módulo FECHA no Orin NX**: todos os 28 streams a taxa cheia, todas as
cadências ≥ alvo (5 inf/s), GPU 72% com ~28% de headroom, térmica folgada (64° vs ~95°+ throttle),
zero streams mortos, zero erros.

## 4. Saturação (degraus de cadência até quebrar)

| Cenário | EPI int | Park int | Qaux int | Qmain drop | FPS EPI | FPS Park | GPU | VDD_IN | Veredito |
|---|---|---|---|---|---|---|---|---|---|
| **prod** | 4 | 4 | 2 | 5 | **31,9** | **30,9** | **72%** | 19,9 W | ✅ produção |
| knee | 3 | 3 | 1 | 4 | 28,5 | 28,1 | **96%** | 23,0 W | ⚠️ limite (entrega já cede) |
| hot | 2 | 2 | 0 | 3 | 25,9 | 25,4 | 99% | 23,2 W | ✗ saturado |
| max | 1 | 1 | 0 | 2 | 17,6 | 22,7 | 99% | 23,0 W | ✗ bem além |

- **Ponto de saturação ≈ +25% de inferência sobre a config de produção** (int3 já encosta em
  GPU 96% e a entrega cai abaixo da taxa da fonte).
- **Degradação graciosa**: mesmo no `max` (2× além do joelho) nenhum stream morre — a entrega
  cai uniformemente (fps_min=fps_avg), sem erros de decoder.
- Potência satura em ~23 W (modo 40W, perfil fan `quiet`, clocks dinâmicos — sem jetson_clocks/sudo).

### Evidência visual (tela física `:1`)

Mosaico dos 3 módulos simultâneos + telemetria ao vivo: EPI 4×4, Estacionamento 4×2,
Qualidade aux 1×2, Qualidade main 1×2 com **ROIs desenhadas (draw-roi) e detecções dentro das
ROIs em coordenadas 4MP**, terminal com GPU/VDD/temp/RAM ao vivo →
`docs/edge/evidence/mm-2026-07-17/mm_mosaico_3modulos.png` (janelas posicionadas via
python-xlib — Mutter ignora window-x/y do sink; landmine documentada).
Telemetria da campanha inteira: `evidence/mm-2026-07-17/telemetry_mm.jsonl` (919 amostras
etiquetadas por cenário) + logs PERF por módulo (`mm_all_prod2_*`, `mm_all_hot_*`).

## 5. Exploração de modelos (item 6 — trava ADR-0043)

Ver `docs/edge/EXPLORACAO_MODELOS_2026-07-17.md` (pesquisa completa, 14 candidatos + fontes).

**Melhor por módulo dentro da trava permissiva (Apache/MIT/BSD):**

| Módulo | Recomendação | Licença | Alternativa | Custo |
|---|---|---|---|---|
| EPI (16) | YOLOX-Tiny INT8 (>600 inf/s) | Apache-2.0 | RF-DETR Small se +mAP | grátis |
| Estacionamento (8) | YOLOX-Tiny/S | Apache-2.0 | D-FINE-N (~190 inf/s) | grátis |
| Qualidade (2-4) | **D-FINE-L/X-Obj365 (57.3/59.3 mAP)** ou RT-DETRv4-X | Apache-2.0 | RF-DETR Large (zero atrito) | grátis |

**Achado central da trava:** D-FINE-X com pretrain Objects365 (**59.3 mAP COCO, Apache código+pesos**)
**supera** o YOLO26-x (57.5, AGPL) de graça — não há razão comercial para AGPL no módulo Qualidade
hoje. **Isolados em "propostas comerciais explícitas" (NUNCA servir silenciosamente):** Ultralytics
Enterprise (~US$5k/ano relatado, não oficial), RF-DETR XL/2XL (PML 1.0), YOLO-NAS (pesos
não-comerciais, descartado), cadeia DINOv3 (DEIMv2 L/X — risco jurídico, exige parecer).
YOLOv9 (GPL), YOLOv10/v12 e Ultralytics v8/11/26 (AGPL) = **proibidos servir** (license-gate mantém).

**Próximo passo:** shootout no box (harness PR #192) D-FINE-S/L × RT-DETRv4-S/X × RF-DETR Small/Large,
medindo AP_small no dataset PPE + amostra Qualidade, antes de fixar o modelo de produção da Qualidade.

## 6. Esqueletos (tasks 108–110) e dashboard (task-112)

**Monofatura (task-108)** — migration 104 (`inspection_sessions`, schema-per-tenant, UNIQUE
piece_id×stage = idempotência da bipagem) + blueprint `/api/v1/monofatura` (scan inbound
idempotente, complete outbound com resultado por atributo + evidência + tempo) + **adaptador
outbound plugável** (`MonofaturaAdapter`, `MONOFATURA_ADAPTER=simulated` — contrato real do
cliente pendente, não trava o stress). Harness de migrations 2x verde (71 testes). 7 testes de rota
+ idempotência real em Postgres.

**Qualidade multi-atributo + Estacionamento (tasks 109/110)** — 4 operações canônicas novas no
`OperationTypeRegistry` existente (task-045, sem roteamento novo):
- `attention_points` (quality): inspeção multi-atributo por ROI **configurável** (lista de pontos
  de atenção = input do cliente, plugável) → resultado por atributo alimenta o outbound monofatura.
- `stage_timer` (quality): cronômetro de etapa entrada→saída com grace de oclusão (via NvDCF track_id).
- `crowd_zone` (counting): aglomeração N+ objetos × M frames consecutivos.
- `dwell_zone` (counting): permanência atípica — **terminologia neutra, v1 faseado, ZERO claim de
  furto** (teste garante que "furto"/"theft" não aparece no output). 12 testes unitários verdes.

**Dashboard integrado (task-112)** — página React dentro da plataforma (recharts + api.ts envelope,
tenant/site-scoped, SocketIO ao vivo): observabilidade de modelos (curvas por época do item 3 +
comparação) + telemetria edge ao vivo (GPU/EMC/temps/rails/fan/RAM/FPS por módulo). Migration 105
(`model_training_metrics` + `edge_telemetry_samples`, públicas com tenant_id, padrão 088). Ingest
edge→Recognition seedado com os JSONL REAIS deste cenário. _(detalhe de commits no fechamento)_

## 7. Landmines novas → REGRAS_PLATAFORMA_JETSON.md

Alimentadas na §3.3 do documento vivo: `interval` ignorado no caminho `input-tensor-from-meta`
(cadência via `drop-frame-interval`); streams mortos silenciosos em conexão RTSP simultânea de
múltiplas instâncias (fix reconnect+stagger); Mutter ignora window-x/y (mover via python-xlib);
YOLOX-Tiny COCO 0.1.1rc0 funciona (dud era específico do Nano); heredoc não-quotado via ssh; e
a §6 nova (reuse-first permanente).
