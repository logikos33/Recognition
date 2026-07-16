---
title: "Edge Jetson: pipelines DeepStream EPI + Contagem (Qualidade após ONNX) — reescreve task-032 — HARDWARE"
pr_title: "feat(edge): pipelines DeepStream no Orin (EPI/Contagem) + TensorRT INT8/DLA"
commit_message: "feat(edge): DeepStream EPI+Contagem no Jetson (RF-DETR/YOLOX)"
eval: manual-hardware
risk: security
requires_hardware: true
supersede: task-032 (OBSOLETA — mini-PC descartado, assumia ultralytics)
depende_de: task-087, task-082, ADR-0044
bloco: 4 (Edge Jetson + VST)
---

# Task 088 — Pipelines DeepStream no Jetson (reescreve 032)

## Objetivo
Rodar EPI e Contagem em DeepStream no Orin, com o detector ONNX Apache (RF-DETR/YOLOX). Qualidade entra depois do
porte ONNX (task-079).

## Escopo
- Pipelines EPI + Contagem; engines TensorRT (INT8/FP16), avaliar **DLA** para descarregar GPU.
- Detecções → Redis local (`detections:*`) → edge-sync-agent.

## Aceite
- [ ] EPI + Contagem processando N câmeras no box; detecções no Redis; sem AGPL.

## Checkpoint
- BLOQUEADA-HARDWARE. Substitui 032. Qualidade fica gated por 079.

## Achados de sessão (2026-07-16) — prep no box real, antes da implementação

**DeepStream 7.1 + TensorRT 10.3 + CUDA 12.6 confirmados funcionando ponta a ponta no Orin NX real:**
smoke test com o sample `deepstream-app` (TrafficCamNet, config de amostra do próprio SDK) rodou 4 streams
simultâneos, ~30 FPS cada, decodificação NVDEC + engine INT8 (build automático a partir de ONNX+calibração) +
tracker NvDCF, renderizado ao vivo no monitor físico do box (HDMI, sessão X11 em `:1`). Confirma que o
hardware/stack está pronto pra pipeline real.

**GAP CRÍTICO pra implementar esta task: não existe parser de bbox nativo do DeepStream pra RF-DETR nem YOLOX.**
- O SDK só traz sample de parser pra família YOLO via **Triton** (`sources/TritonOnnxYolo`, YOLOv3, plugin
  `nvinferserver` — precisa de servidor Triton sidecar, mais pesado) — nada pro `nvinfer` nativo.
- RF-DETR (saída `pred_logits`/`pred_boxes`, estilo DETR) e YOLOX (saída raw `[N, 5+C]`, precisa decode de
  grid+stride) **não são formatos que o `nvinfer` entende sem um parser C customizado**
  (`NvDsInferParseCustom...`, compilado como `.so`, via `parse-bbox-func-name`). Isso é o trabalho real desta
  task — não é "ligar o detector", é escrever esse parser (ou portar um existente pra RF-DETR/YOLOX).

**Caminho alternativo validado (fora do DeepStream nativo) — útil como referência de implementação:**
TensorRT puro via Python (`tensorrt` bindings, já instalados no box — 10.3.0 — mais `pycuda` pra gerenciamento
de buffer CUDA, `pip install pycuda` compila contra o toolkit já instalado sem sudo) roda um `.engine` YOLOX
a **165-200 FPS de inferência** (vs. <1 FPS via ONNXRuntime CPU-only — o wheel `onnxruntime-gpu` genérico do
PyPI **não tem execution provider CUDA/TensorRT pra Jetson/aarch64**; o índice `pypi.jetson-ai-lab.dev` que
teria wheels específicos da NVIDIA pra JetPack 6/CUDA 12.6 **não resolveu** na rede do box — não investigar
mais essa rota sem confirmar a URL certa primeiro). Padrão de código: `context.set_tensor_address()` +
`execute_async_v3()` (API TensorRT 10.x). Isso prova que a via "Python + TensorRT direto" é viável como
alternativa ao parser C nativo do `nvinfer`, se for mais rápido de implementar que o parser customizado —
decisão de arquitetura pra quem pegar esta task.

**Checkpoints públicos de teste — CUIDADO, não reusar sem revalidar:** os únicos `.onnx` prontos pra baixar
sem precisar de `torch` são os releases antigos da Megvii (`0.1.0`/`0.1.1rc0`, 2021,
`github.com/Megvii-BaseDetection/YOLOX/releases`) — testados (`yolox_nano.onnx` e `yolox_s.onnx`) e ambos
com **objectness anormalmente baixo** mesmo com preprocessing corrigido (normalização ImageNet confirmada
contra `yolox/data/data_augment.py` da própria Megvii nessa tag) — causa raiz não identificada (não é
FP16 — testado FP32 também, mesmo padrão; não é ordem de canal — testada hipótese alternativa, também não
bateu). **Não bloqueia a task**: o checkpoint real virá da task-086 (treino próprio), não de artefato público
genérico. Só documentando pra não perder tempo re-testando o mesmo checkpoint.
