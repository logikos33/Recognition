---
title: "F7 — DeepStream: pipeline lê config em runtime (decisão do Vitor)"
commit_message: "feat(deepstream): pipeline lê config do cenário em runtime + hot-reload (F7)"
eval: default
risk: security
---

# F7 — DeepStream configurado pelo banco

## Objetivo
`deepstream/` tem só parser YOLOX + `.gitkeep`; falta o elo config→pipeline.

## Critérios de aceitação
- [x] **Decisão do Vitor:** o pipeline **lê a config em runtime** (não gerar `.txt` estático) — consulta a config entregue pelo `/config/poll` e recarrega localizado (padrão `model_watcher`), permitindo hot-reload sem reiniciar.
- [ ] Pipeline DeepStream consome a config do cenário (nvinfer parametrizado a partir do banco via config entregue).
- [ ] Reload sem restart do device.

## Invariantes de segurança
- Zero AGPL/ultralytics no caminho servido (só ONNX Apache — YOLOX/RF-DETR).

## Arquivos no escopo
- `deepstream/**`, `services/inference/**`
