# Task 055 — Remover AGPL do Caminho Servido + Gate de Licença CI

**Status**: IN PROGRESS (PR aberto — feat/task-055a-license-gate-remove-agpl-serving)
**Risk**: security (mudança de detector no caminho crítico de inferência)
**Branch**: feat/task-055a-license-gate-remove-agpl-serving

## Objetivo

Remover `ultralytics` (AGPL-3.0) do caminho de produção servido, permitindo
comercialização do produto sem restrições copyleft. Adicionar gate de CI permanente.

## Sub-tasks

### 055a — Gate de licença CI + remover ultralytics de serving (ESTA TASK)

- [x] `requirements/worker.txt` — ultralytics removido, onnxruntime adicionado
- [x] `requirements/inference.txt` — ultralytics removido, onnxruntime adicionado
- [x] `services/api/app/infrastructure/queue/tasks/quality_inference.py`
      — ImportError retorna gracefully (não retries) em vez de loop infinito
- [x] `scripts/check_license_gate.py` — gate local + gera THIRD_PARTY_NOTICES
- [x] `.github/workflows/ci.yml` — job `license-gate` adicionado (falha se AGPL no serving)
- [ ] PR criado + CI verde

### 055b — ONNX Detector Factory (PR A1 do plano)

Implementar `services/api/app/domain/detectors/`:
- `base.py` — protocolo `Detector.predict(frame) -> list[dict]`
- `onnx_yolox.py` — ONNXRuntime, pré/pós-proc, NMS, mapeamento EPI classes
- `onnx_rfdetr.py` — ONNXRuntime RF-DETR
- `factory.py` — `get_detector(backend, model_path, classes)`
Refatorar `inference.py::inference_loop` para usar factory.
Env: `DETECTOR_BACKEND=yolox_onnx|rfdetr_onnx|ultralytics` (default: yolox_onnx).

### 055c — Remover ultralytics de training.py (após decisão ADR-0024)

Manter ultralytics em `requirements/training.txt` até detector EPI treinado estar validado.
Após validação → migrar treinamento para YOLOX nativo.
Ver: `docs/decisions/adr/0024-detector-license-apache-migration.md`

## Aceite 055a

- CI job `license-gate` verde (PASSED)
- `grep -r "ultralytics" requirements/{api,worker,inference,celery-worker}.txt` → sem resultado
- inference.py e quality_inference.py funcionam sem ultralytics (no-YOLO mode)
- THIRD_PARTY_NOTICES.txt gerado como artifact de CI

## Referências

- ADR-0024: `docs/decisions/adr/0024-detector-license-apache-migration.md`
- Plan: plano E2E na nuvem com câmeras sintéticas (`.claude/plans/`)
