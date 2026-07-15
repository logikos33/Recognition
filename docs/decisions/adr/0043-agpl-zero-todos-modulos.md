# ADR-0043 — AGPL-zero em todos os módulos (caminho servido = Apache)

**Status:** Aceito · **Data:** 2026-07-14 · **Autores:** Vitor Emanuel (Logikos)
**Estende:** ADR-0001 (DeepStream vs Ultralytics) · **Relaciona:** ADR-0044, ADR-0047

## Contexto
O caminho servido de EPI já migrou pra ONNX (task-055a). Porém o módulo **Qualidade** ainda faz
`from ultralytics import YOLO` (`quality_training.py`, `quality_inference.py` — filas Celery servidas), o peso
AGPL `yolov8n.pt` está commitado na raiz e docs/env ainda citam `INFERENCE_ENGINE=ultralytics`. O license-gate
só inspeciona **requirements**, não **imports** — então esse acoplamento AGPL passa despercebido.

## Decisão
**Nenhum módulo** (EPI, Qualidade, Contagem) pode conter AGPL no caminho servido. O detector servido é sempre
Apache (RF-DETR/YOLOX ONNX — ADR-0044). Ultralytics só é tolerado em ferramentas de treino **offline**
(`training.txt`), nunca importado por código servido.

## Consequências
- Portar Qualidade pra ONNX (task-079); remover `yolov8n.pt` e limpar docs/env (task-080).
- Estender o license-gate pra escanear **imports** de pacotes AGPL no caminho servido (task-081).
- Enquanto Qualidade não portar, seu caminho de inferência fica **desativado** (não "quebrado em runtime").
