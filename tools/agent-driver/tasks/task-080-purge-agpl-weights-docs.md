---
title: "AGPL-zero: remover yolov8n.pt do repo e limpar docs/env (INFERENCE_ENGINE=ultralytics)"
pr_title: "chore(license): remover pesos AGPL e referências a ultralytics nas docs/env"
commit_message: "chore(license): purga yolov8n.pt + limpa docs/env do caminho ultralytics"
eval: default
risk: security
depende_de: ADR-0043, task-079
bloco: 1 (AGPL-zero)
---

# Task 080 — Purga de pesos AGPL + limpeza de docs/env

## Objetivo
Tirar do repositório os pesos AGPL e as referências que induzem ao caminho ultralytics.

## Escopo (confirmado — C-04)
- Remover `yolov8n.pt` (e `yolov8n.onnx` se derivado de pesos AGPL) da raiz do repo.
- Limpar `services/inference/AGENT.md`, `inference/AGENTS.md`, `.env.example` e demais que citam
  `INFERENCE_ENGINE=ultralytics` / `YOLO_MODEL_PATH=yolov8n.pt` como caminho válido.
- Atualizar `THIRD_PARTY_NOTICES.txt` e o README (nota de licença) refletindo o caminho 100% Apache.

## Aceite
- [ ] `grep -ri ultralytics` no caminho servido = 0 (fora de training.txt); pesos AGPL fora do repo; docs coerentes.

## Checkpoint
- STOP-for-review. Depende de 079 (código de Qualidade já portado).
