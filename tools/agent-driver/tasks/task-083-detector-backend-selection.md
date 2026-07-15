---
title: "Detector: seleção de backend (RF-DETR/YOLOX) por câmera/modelo + hot-reload"
pr_title: "feat(models): backend de detecção selecionável por câmera com hot-reload"
commit_message: "feat(models): arquitetura de detecção no registry + resolução por câmera"
eval: default
risk: security
depende_de: task-082, task-045 (seleção de modelo por câmera)
bloco: 2 (Detector)
---

# Task 083 — Seleção de backend por câmera/modelo

## Objetivo
Permitir escolher a arquitetura (RF-DETR/YOLOX) por câmera/modelo, reusando o mecanismo de model-config
(task-045) e o hot-reload Redis existente.

## Escopo
- Estender o registry/model-config com `arch` (rf_detr|yolox); resolução do detector efetivo por câmera.
- Hot-reload já existe (`camera:model:{id}` + pub/sub) — propagar a arquitetura junto.

## Aceite
- [x] Trocar a arquitetura por câmera aplica sem restart; testes; UI reflete o backend efetivo.

## Checkpoint
- STOP-for-review.

## Status (2026-07-14)

**Investigação C-04 — o que já existia:**

- A cascata de resolução por câmera JÁ EXISTIA e já cumpria o essencial do
  escopo: `services/api/app/infrastructure/queue/tasks/inference.py::
  _resolve_camera_model` / `_get_detector_for_camera` (WS-A6, mergeada antes
  desta task) resolve `model_deployments` ativo → `cameras.model_{module}_id`
  → `trained_models.framework` + `r2_onnx_key` → `factory.get_detector(backend=
  framework, ...)`. Não existe uma coluna `arch` separada — `framework`
  ("yolox"/"rfdetr", migration 098) já cumpre esse papel; não foi duplicada.
- Cache do detector é keyed por `model_id` (não por framework isolado) — como
  framework é propriedade do registro do modelo, qualquer troca de
  arquitetura implica troca de `model_id`, e o cache já invalida sozinho ao
  detectar `model_id` diferente, além da invalidação explícita via pub/sub
  Redis `camera:model_change:{camera_id}` (publicada por
  `cameras/model_handlers.py::_notify_model_assignment`). **Aplica sem
  restart, no mesmo processo worker** — confirmado e agora coberto por teste
  explícito (ver abaixo).
- Task-079 (Qualidade) já reusa o MESMO `_get_detector_for_camera` — não há
  caminho duplicado ou divergente entre EPI e Qualidade.
- `services/inference/` (task-082, standalone) tem hot-reload próprio via
  canal Redis `model:reload`, mas carrega UM detector por processo (não por
  câmera) — **confirmado que NÃO está em produção**: `railway_start.py` só
  aceita `SERVICE_TYPE` em `api | worker | celery-worker | beat |
  pre-annotation | landing-page`; `services/inference` não é nenhum desses.
  É código legado/standalone, não deployado. Documentado aqui para não ser
  confundido com o caminho servido real.

**Gap real confirmado e fechado:**

- A UI não mostrava o backend efetivo em lugar nenhum (`grep -rn "framework"
  apps/frontend/src` não retornava nada antes desta task). Causa raiz: o
  endpoint que alimenta `CameraModelAssignment.tsx` (`GET /training/models`
  → `TrainingRepository.get_models_by_user`) nunca selecionava
  `tm.framework` — o dado nem chegava ao frontend.
- Fechado com:
  1. `training_repository.py::get_models_by_user` agora seleciona
     `tm.framework` (SELECT explícito, sem migration — coluna já existe
     desde a 098).
  2. `CameraModelAssignment.tsx` mostra um `Badge` ("YOLOX"/"RF-DETR") ao
     lado do módulo quando a câmera tem um modelo atribuído com framework
     conhecido; nada é mostrado quando não há atribuição (fallback env) ou
     o modelo é legado sem `framework`.

**Testes adicionados:**
- `test_inference_model_resolution.py::TestGetDetectorForCamera::
  test_troca_de_arquitetura_por_camera_aplica_sem_restart` — cobre
  explicitamente troca YOLOX→RF-DETR no mesmo processo, sem restart
  (aceite da task).
- `test_repositories.py::TestTrainingRepository::
  test_get_models_by_user_seleciona_framework` — trava a coluna no SELECT.
- `CameraModelAssignment.test.tsx` — 3 novos testes: badge aparece com
  modelo atribuído, não aparece com modelo padrão, e troca ao vivo
  (YOLOX→RF-DETR) sem remount do componente.

**Premissa da spec que se mostrou incorreta:** o texto "Estender o
registry/model-config com `arch` (rf_detr|yolox)" sugeria uma coluna nova.
Não foi criada — `trained_models.framework` já existe e já é usado pela
cascata (reuse > duplicação, conforme instrução explícita da task).
