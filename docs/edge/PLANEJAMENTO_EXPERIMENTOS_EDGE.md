# Planejamento dos experimentos no edge (Jetson) — conhecimento consolidado

> Consolida as decisões, explicações e achados da sessão de planejamento (2026-07-16), pra não se perder.
> Complementa `STATUS_2026-07-16_jetson_handson.md` e as tasks 084/087/088/100/101/102/103/104.

## 1. Onde estamos (estado validado no box)
- Stack de inferência **provado no hardware**: DeepStream 7.1 sample rodou (4 streams @ ~30fps, NVDEC + INT8 + tracker).
- Parser YOLOX custom escrito/validado (task-088). Telemetria idle×inference capturada (idle ~4.3W/0% GPU → inferência ~13W/63% GPU).
- Benchmark inicial: YOLOX-Nano FP16 = **310 qps / 3,4ms** (placeholder; modelo real é mais pesado).

## 2. Sequência de experimentos (ordem bloqueante)
**103 (prontidão GO/NO-GO) → 104 (DLA eval) → 101 (tempo de treino) → 102 (stress 28 câmeras).** Não pular 103/104.
Insight: o stress *que vale* quer o modelo real (da 101); mas dá pra rodar o stress GPU-only com modelo leve antes
(teto) e re-rodar com o real depois.

## 3. Quando o Jetson conecta no Recognition
Hoje o box roda **standalone** (DeepStream + telemetria local). A conexão com o Recognition acontece em etapa
própria, **não** é pré-requisito dos experimentos locais (101/102 renderizam na tela do próprio box):
- **Cloud já pronto** (waves antigas, em produção): enrollment (003/004), heartbeat ingest (002), fleet/health (016-018).
- **Falta o lado do edge:** `edge-sync-agent` real (**task-034**) apontando pra API + ingest de telemetria (**099/100**),
  gated por **enrollment do device** (pega o JWT). É aí que o box passa a aparecer no Recognition.
- **Para o gráfico de telemetria aparecer NO Recognition** (não só na tela do box) → precisa dessa conexão (034 + ingest 099/100).
  Para os experimentos na tela do Jetson → **não** precisa.

## 4. DLA — o que é e a decisão
- **DLA = Deep Learning Accelerator**; o Orin NX tem **2 núcleos**, separados da GPU. Rodar parte da inferência no DLA
  **libera a GPU** → mais câmeras no mesmo box (capacidade "de graça" se ociosa).
- **Porém:** o DLA só suporta um subconjunto de ops. Cabeças modernas (YOLOX/DETR) usam ops não-suportadas → caem
  pra GPU ("fallback") → aí o DLA fica **mais lento** (benchmark: DLA 102 qps vs GPU 310). Pra valer, precisa de
  modelo **"DLA-clean"** (todas as camadas suportadas).
- **Decisão (task-104):** caracterizar o fallback e decidir GPU-only vs DLA-augmented **antes** do stress. O DLA-clean
  do nosso modelo depende do modelo treinado (101) → stress roda GPU-only primeiro, re-roda com DLA depois.

## 5. YOLOX — variantes (COCO val)
| Modelo | Params | GFLOPs | mAP | Entrada | Uso |
|---|---|---|---|---|---|
| Nano | 0,91M | 1,08 | 25,8% | 416 | mobile; placeholder do benchmark |
| **Tiny** | 5,06M | 6,45 | 32,8% | 416 | **experimento de treino** (rápido) |
| **S** | 9,0M | 26,8 | 40,5% | 640 | **sweet spot produção edge** |
| M | 25,3M | 73,8 | 46,9% | 640 | pesado p/ 28 cams no Orin NX |
| L | 54,2M | 155,6 | 49,7% | 640 | nuvem/acurácia |
| X | 99,1M | 281,9 | 51,1% | 640 | maior; inviável em 28 cams edge |
| Darknet53 | 63,7M | 185,3 | 47,7% | 640 | legado (YOLOv3+cabeça YOLOX) |
- Experimento → **Tiny**. Produção EPI → provável **S**. RF-DETR = alvo de acurácia (ADR-0044), YOLOX-S = fallback maduro.

## 6. Dataset (experimento de treino)
- Classes-alvo RVB: **óculos de proteção, luvas, protetor auricular, jaleco**. Cenário lab/fábrica, não construção.
- Público que cobre a maioria: **"PPE Dataset for Workplace Safety" (SiaBar, Roboflow)** (óculos + luvas + ear-protection);
  **"Safety_PPE"** cobre **jaleco/lab coat** + luvas + goggles. Export **COCO** (YOLOX). Download = Roboflow API key (passo externo).
- **⚠️ Risco real — protetor auricular INTRA-AURICULAR (plug):** praticamente inexistente em dataset público e
  **difícil de detectar por CFTV** (minúsculo, oculto por orelha/cabelo). "Ear-protection" público = **abafador (concha)**.
  Para a RVB: alinhar expectativa; considerar proxy (mão→orelha, cordão) ou aceitar classe fraca. **Tratar à parte no modelo real.**
- Para o **experimento de tempo de treino**, a classe exata importa pouco — usar SiaBar + YOLOX-Tiny e medir.

## 7. Câmera
- Intelbras na bancada. RTSP típico: `rtsp://user:senha@IP:554/cam/realmonitor?channel=1&subtype=0` (subtype=1 = substream).
- ONVIF costuma vir **desligado de fábrica** (achado do Code) — habilitar no web da câmera ou usar a URL RTSP direto.
- **Substream vs full (1080p):** decisão de dimensionamento — inferir em substream reduzido muda drasticamente o que cabe
  nas 28 câmeras. Definir alvo de FPS/resolução por câmera antes do stress (task-067/102).

## 8. Visualização na tela do Jetson (requisito do Vitor)
- Experimentos devem renderizar no **monitor físico** (DISPLAY=:1, XAUTHORITY=/run/user/1000/gdm/Xauthority):
  progresso/telemetria do treino (101) e **mosaico das 28 câmeras + gráfico de telemetria ao vivo** (102).

## 9. Treino no Jetson — natureza
- É **experimento** (medir tempo/curva), não produção. Jetson = inferência; treino de produção = GPU off-box (task-086).
- Env: PyTorch-for-Jetson + YOLOX (Apache). **ZERO ultralytics** (ADR-0043).
