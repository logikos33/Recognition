# ADR-0040 — Edge ancorado em Jetson Platform Services (DeepStream + VST + DLA)

**Status:** Proposta · **Data:** 2026-07-12 · **Estende:** ADR-0025 (hardware Orin), ADR-0022 (VMS/live)
· **Relaciona:** ADR-0034 (NVR/DVR replay), ADR-0028 (evidência R2 / storage no edge),
ADR-0033 (clips de evidência), ADR-0039 (compute de treino no edge), ADR-0020 (uplink/túnel),
ADR-0031 (Training Studio — pré-anotação), edge-sync-agent, pasta `deepstream/`.

## Contexto

O edge definido pra produção é o **Palit Pandora NVIDIA Jetson Orin NX Super 16GB (A002FV1P1)**:
8-core Arm Cortex-A78AE · GPU Ampere 1024 CUDA + 32 Tensor cores · **2× DLA** · PVA · ISP ·
**CODEC de vídeo por hardware (H.264/H.265 encode+decode)** · 16GB LPDDR5 · M.2 128GB (SO+app) +
2º M.2 Gen4x4 (SSD ou placa de captura) · 2× GbE · slots WiFi e 5G/4G · **157/78 TOPS (Sparse/Dense)
INT8 em Super Mode** (JetPack 6.2, MAXN_SUPER; TensorRT 10.3, DLA 3.1).

O ponto estratégico: o **NVIDIA Jetson Platform Services (JetPack 6.x)** entrega, prontos, microserviços
que hoje pensávamos construir na unha — **DeepStream** (inferência multi-stream), **Video Storage
Toolkit / VST** (ingestão ONVIF + gravação + streaming WebRTC/RTSP), **API/IoT Gateway**, **Message Bus
(Redis)**, **Monitoring**, **Zero-Shot Detection** e **VLM Inference**, além de reference workflows
(**AI-NVR**, alertas Gen-AI). Muito disso mapeia ~1:1 no Recognition (VMS, inferência N câmeras,
gravação NVR/DVR, evidência, alertas).

Construir tudo custom duplica o que a NVIDIA já mantém, e diverge do padrão que torna o produto
"Jetson-native" (mais robusto e mais fácil de vender).

## A stack JetPack (referência)

Hardware Orin (GPU/CPU/**DLA**/PVA/ISP/**CODEC**) → Jetson Linux (Ubuntu L4T + Security) →
**AI Stack** (50+ modelos pré-treinados, VIT, LLM) **+ Jetson Platform Services** (microserviços:
AI Analytics, **DeepStream AI Perception**, **Zero-Shot Detection**, **VLM Inference**,
**Video Storage Toolkit**, **API/IoT Gateway**, Monitoring, **Message Bus REDIS**, Networking, Firewall)
→ Reference Workflows (**AI-NVR**, alertas Gen-AI) → **Nossa aplicação**.

## Decisão

**Ancorar a camada de edge do Recognition no Jetson Platform Services** — adotar **DeepStream** para
inferência, **VST** para a camada de câmera (ingestão/gravação/streaming) e **DLA** para offload de
inferência — e fazer o `edge-sync-agent` + a nuvem **consumirem** desses serviços, em vez de reimplementar.

### Mapeamento — o que ADOTAR vs o que MANTER nosso

| Serviço NVIDIA | Cobre | Ação | O que MANTEMOS nosso |
|---|---|---|---|
| **DeepStream AI Perception** | Pipeline de inferência multi-câmera (TensorRT) no edge | **Adotar** como motor de inferência (usar a pasta `deepstream/`) | Detector treinado (RF-DETR/**YOLOX** ONNX→TensorRT), classes/limiares por operação (ADR-0032), regras de alerta |
| **Video Storage Toolkit (VST)** | Descoberta ONVIF, gravação, streaming (WebRTC/RTSP), replay | **Adotar/avaliar** no lugar do `camera-gateway` + RTSP→HLS custom; casa com ADR-0034 (replay NVR/DVR) | Cadastro de câmera/gravador na nossa modelagem multi-tenant, política de retenção, UI de timeline (ADR-0034) |
| **CODEC de vídeo (hardware)** | Encode/decode H.264/H.265 | **Adotar** pra transcode/live/clips no hardware (não CPU/ffmpeg) — resolve o custo de transcode do live | Regras de duração/retenção dos clips (ADR-0033), destino R2 (ADR-0028) |
| **DLA (2 cores)** | Acelerador dedicado de inferência | **Adotar** offload de camadas → libera GPU pra sustentar N câmeras | Escolha de quais modelos/camadas caem no DLA (compat. de layers) |
| **Zero-Shot Detection + VLM Inference** | Detecção sem treino (texto) + descrição de cena | **Avaliar** como backend de **pré-anotação** (ADR-0031, candidato mais barato que DINO+SAM) e como **alertas generativos** (diferencial) | Fluxo de anotação/HITL, Training Studio, feature flag da pré-anotação (ADR-0035) |
| **API/IoT Gateway + Message Bus (Redis) + Monitoring** | Plumbing edge↔nuvem, eventos, telemetria | **Alinhar** o edge-sync-agent a esses canais (já usamos Redis) | Contrato de eventos, heartbeat/frota, presigned upload (device token RS256, ADR-0028) |
| **AI-NVR (reference workflow)** | Padrão de NVR pronto | **Referência** de arquitetura pro VMS | Nosso VMS multi-tenant / UX |

### Restrições de compatibilidade (o que ajustar no nosso sistema)

1. **JetPack 6.2 + MAXN_SUPER** como baseline do edge (157 TOPS); confirmar que o módulo não é revisão
   legada antes de prometer o número.
2. **Detector servido via TensorRT/DeepStream:** o ONNX (nada de `ultralytics`/AGPL no caminho servido)
   compila pra engine TensorRT **on-device**. **YOLOX** tem caminho DeepStream/TensorRT muito mais
   maduro que o RF-DETR (DETR converte pior) → **benchmarkar YOLOX pro edge**; RF-DETR segue ótimo pra
   treinar/validar (weekend MVP). Ver TRAINING_PIPELINE_WEEKEND_MVP.md.
3. **Storage no edge (ADR-0028 inalterado):** M.2 128GB = **SO + app, NÃO storage**; evidência → R2.
   O **2º M.2 Gen4x4** hospeda o **ring buffer transitório** (NVMe), com a **reserva de espaço livre**
   (guard anti-travamento) mantida. O 2º slot também aceita **placa de captura** → ingestão de câmera
   **analógica** direto no box (caso DVR analógico).
4. **Rede:** 2× GbE (LAN de câmeras + uplink) e **slot 5G/4G** → **site remoto sem internet cabeada**
   viável (o box sobe via 5G); combina/complementa o túnel outbound (ADR-0020).
5. **Treino no edge (ADR-0039):** **GPU treina** (fine-tune pequeno); **DLA é só inferência**. Isolar
   recursos — treino usa GPU; inferência ao vivo usa DLA + GPU — pra não engasgar o monitoramento.

## Consequências / trade-offs (honestos)

- **A favor:** multi-stream, replay NVR, transcode em hardware, ONVIF e telemetria **quase de graça**;
  edge mais robusto e alinhado ao padrão NVIDIA (argumento comercial "Jetson-native").
- **Contra:** acoplamento ao stack NVIDIA (DeepStream/VST têm curva e são específicos do Jetson) —
  **mitigar** mantendo nosso detector/modelagem/UX desacoplados atrás de interfaces, pra não amarrar o
  domínio ao SDK.
- **Risco de escopo:** avaliar VST não é "trocar tudo hoje" — é um **spike** antes de comprometer.
  Enquanto isso, o `camera-gateway` + RTSP→HLS atual continua servindo o live.
- **DeepStream × treino no mesmo box:** contenção de GPU — reforça o isolamento treino×inferência
  (ADR-0039).

## Faseamento (roadmap — não bloqueia a pipeline em curso)

1. **Spike DeepStream:** rodar o ONNX (YOLOX) → engine TensorRT → DeepStream multi-stream num Orin de
   teste; medir fps/câmeras e offload no DLA.
2. **Spike VST:** validar ONVIF/gravação/WebRTC + replay (ADR-0034) num NVR real; decidir adotar vs
   manter o gateway custom.
3. **Alinhar edge-sync-agent** ao API/IoT Gateway + Message Bus (Redis) + Monitoring.
4. **Avaliar Zero-Shot/VLM** como backend de pré-anotação (flag off por padrão, ADR-0031/0035) e como
   alertas generativos.

## Referências

ADR-0025, ADR-0022, ADR-0034, ADR-0028, ADR-0033, ADR-0039, ADR-0020, ADR-0031, ADR-0035;
`deepstream/`; TRAINING_PIPELINE_WEEKEND_MVP.md.
Specs: Palit Pandora A002FV1P1 (palit.com/pandora) · JetPack 6.2 Super Mode (developer.nvidia.com) ·
DeepStream / VST / Jetson Platform Services (docs.nvidia.com).
