# ADR 0001 — DeepStream vs Ultralytics para Inferência de Borda

## Status

Aceito

## Data

2026-05-27

## Contexto

A plataforma Recognition precisa executar inferência YOLO em tempo real sobre streams de câmeras CCTV. Duas opções principais foram avaliadas:

- **NVIDIA DeepStream**: pipeline GStreamer-nativo, otimizado para GPU NVIDIA (TensorRT, CUDA), latência mínima, requer hardware NVIDIA dedicado.
- **Ultralytics YOLOv8**: biblioteca Python pura, suporta CPU e GPU via PyTorch, mais simples de operar em ambientes sem GPU.

O ambiente de produção de clientes como RVB Isolantes possui edge boxes com GPU NVIDIA. O ambiente de desenvolvimento e CI/CD roda em máquinas sem GPU dedicada, incluindo o Railway worker (CPU-only).

## Decisão

Adotar **ambos os backends**, selecionáveis pela variável de ambiente `INFERENCE_ENGINE`:

- `INFERENCE_ENGINE=deepstream` → pipeline DeepStream (produção edge com GPU NVIDIA)
- `INFERENCE_ENGINE=ultralytics` → Ultralytics YOLOv8 Python (dev, staging, CI, cloud worker CPU)

Ambos os backends publicam resultados no mesmo canal Redis pub/sub (`detections:{camera_id}`), de modo que a camada de API e o frontend são agnósticos ao engine utilizado.

## Consequências

- Melhor desempenho em produção edge: DeepStream com TensorRT alcança latência sub-100 ms por frame.
- Desenvolvimento e CI possíveis sem hardware NVIDIA: Ultralytics roda em CPU com desempenho suficiente para testes.
- Dois backends a manter: mudanças no formato de saída de detecções devem ser refletidas em ambos.
- O contrato de interface (schema Redis pub/sub) precisa ser versionado e documentado para garantir compatibilidade entre os dois engines.
- Testes de integração em CI usam `INFERENCE_ENGINE=ultralytics` por padrão.
