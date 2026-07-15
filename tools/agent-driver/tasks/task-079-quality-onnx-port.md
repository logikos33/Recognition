---
title: "AGPL-zero: portar módulo Qualidade de ultralytics para ONNX (Apache) — MIGRATION? não"
pr_title: "fix(quality): remover ultralytics do caminho servido; inferência/treino via ONNX (RF-DETR/YOLOX)"
commit_message: "fix(quality): Qualidade sai do ultralytics para detector ONNX Apache"
eval: default
risk: security
gate: STOP-for-review (fluxo de treino)
depende_de: ADR-0043, ADR-0044
bloco: 1 (AGPL-zero)
---

# Task 079 — Portar Qualidade para ONNX (AGPL-zero)

## Status
PR aberto para `develop` — branch `agent/task-079-quality-onnx-port`. Aguardando revisão humana
(risk:security — STOP-for-review). Link do PR a preencher após `gh pr create`.

## Objetivo
Remover `from ultralytics import YOLO` do caminho servido da Qualidade e usar o detector ONNX Apache
(RF-DETR/YOLOX) — igual ao EPI.

## Contexto (confirmado — C-04)
- `services/api/app/infrastructure/queue/tasks/quality_inference.py` (linhas ~272, ~552) e
  `quality_training.py` (~218) fazem `YOLO("yolov8n.pt")`. Estão nas filas `quality_inference`/`quality_training`
  (servidas). Import lazy → hoje quebraria em runtime (ultralytics não está no worker.txt).
- O detector servido está em `services/inference/inference/detectors.py` (ONNX).

## Escopo
- Substituir a inferência de Qualidade pelo detector ONNX (reusar o de `services/inference` ou o registry por
  módulo). Treino de Qualidade passa a produzir/consumir ONNX (ver task-086).
- Remover qualquer `import ultralytics` do caminho servido de Qualidade.

## Eval
- Teste: task de `quality_inference` roda sem ultralytics instalado; detecta via ONNX; sem ImportError.
- license-gate (task-081) verde; pytest + ruff verdes.

## Aceite
- [x] Qualidade sem ultralytics no servido; inferência via ONNX; testes verdes. PR para develop.

## Notas de implementação
- `quality_inference.py` e `quality_training.py` reusam `_get_detector`/`_get_detector_for_camera`
  de `tasks/inference.py` (mecanismo já genérico por `active_module`, não duplicado).
- OK/NOK agora por NOME de classe (`QUALITY_CLASSES`/`category="ok"`), não índice — `defect_class`
  vira string (coluna já é VARCHAR).
- `run_quality_training_pipeline`: dataset ainda é montado, mas o treino real fica desativado
  (`status=failed`, `reason=training_pending_task_086`) até a task-086 (RF-DETR ONNX training).
- Ver detalhes completos no corpo do PR (seção "Security review").

## Checkpoint
- STOP-for-review (risk:security, toca detecção). Sem migration.
