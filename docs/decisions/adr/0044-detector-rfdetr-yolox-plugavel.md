# ADR-0044 — Detector servido: RF-DETR (default acurácia) + YOLOX (throughput/DLA), plugável

**Status:** Aceito · **Data:** 2026-07-14 · **Autores:** Vitor Emanuel (Logikos)
**Relaciona:** ADR-0001, ADR-0040 (edge Jetson), ADR-0043 (AGPL-zero)

## Contexto
`services/inference/detectors.py` documenta "YOLOX-S e RF-DETR-N" mas só implementa `YoloxOnnxDetector`.
Decisão de produto: modelos Apache, portáteis, "cada cliente treina o próprio". Alvo de acurácia = RF-DETR
(Apache, SOTA 2025, roda em Jetson). Restrição de edge: Orin NX 16GB, 28 câmeras.

## Decisão
- **RF-DETR** = default de acurácia (implementar de fato — decoder/post-proc — task-082).
- **YOLOX** = opção de throughput e fallback no edge (CNN, maduro em TensorRT/DeepStream, **descarrega no DLA**,
  INT8 limpo). Mantido.
- Backend **plugável** por câmera/modelo (a interface já abstrai); o **default de produção é decidido por
  benchmark no hardware real** (task-084: RF-DETR vs YOLOX, GPU vs DLA, FP16 vs INT8, 28 streams).
- **Sem modelos pré-treinados do TAO no núcleo:** licença NVIDIA Open Model (não-Apache) amarra a NVIDIA e
  fere a portabilidade. TAO só como conveniência de treino, se algum dia.

## Consequências
- RF-DETR família DETR é mais pesado e ops de transformer tendem a cair da DLA pra GPU → benchmark decide.
- Registry/model-config por câmera precisa carregar a arquitetura junto do peso.
