# Task 054 — Pipeline de Treino E2E (Vast.ai → Registry → Deploy)

**Status**: PENDING
**Risk**: security (credenciais Vast.ai, acesso R2, modelos em produção)
**Branch**: feat/task-054-training-pipeline-e2e

## Objetivo

Provar o pipeline completo de treinamento: dataset PPE → Vast.ai GPU → YOLOX/RF-DETR ONNX →
R2 storage → registry (`models` table) → deploy via admin console.

## Pré-requisitos

- `VAST_API_KEY` configurado via env/CLI (nunca commitado)
- Credenciais R2 em env (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `R2_BUCKET`)
- task-055a (ONNX detector factory) mergado antes desta task

## Entregáveis

- [ ] `training/vast/provision.py` — provisiona GPU spot Vast.ai (RTX 3090/4090 mín.)
- [ ] `training/vast/train_yolox.py` — treina YOLOX-s no dataset PPE comercial-friendly
- [ ] `training/vast/train_rfdetr.py` — treina RF-DETR-N no mesmo dataset
- [ ] `training/vast/export_onnx.py` — exporta pesos → ONNX + valida com onnxruntime
- [ ] `scripts/register_pretrained_models.py` — sobe ONNX para R2, insere em `models` com linhagem
- [ ] `docs/datasets/PPE_LICENSE.md` — licença do dataset registrada
- [ ] Substituição real de `_dispatch_vast_ai` (atualmente simulação em training.py)
- [ ] Métricas: mAP + recall `no_helmet` por modelo registradas em `models.metrics`

## Aceite

- `training_job` com status `completed` e métricas reais no banco
- ONNX+pesos no R2 com linhagem (dataset_version → treino → modelo)
- E2E com 4 câmeras usando o modelo EPI treinado (task-052 + este)

## Débito técnico resolvido

- `_dispatch_vast_ai` em `services/api/app/infrastructure/queue/tasks/training.py`
  é atualmente simulação com log `warning` (registrado em CLAUDE.md, Sprint 2026-04-13)
