---
title: "Treino LGPD-clean: pipeline RF-DETR (Vast.ai/local) → export ONNX → registry; Roboflow opcional"
pr_title: "feat(training): treino RF-DETR com export ONNX; Roboflow atrás de flag+DPA"
commit_message: "feat(training): pipeline de treino RF-DETR Apache → ONNX → registry"
eval: default
risk: security
depende_de: ADR-0047, ADR-0044, task-085
bloco: 3 (Treino LGPD-clean)
---

# Task 086 — Pipeline de treino RF-DETR

## Objetivo
Treinar RF-DETR (open-source Apache) no compute atual, exportar ONNX, registrar — sem depender do Roboflow cloud.

## Escopo
- Treino RF-DETR (dataset COCO versionado) via TrainingCompute (Vast.ai/local — ADR-0039) → export ONNX → registry/linhagem.
- Roboflow cloud = opcional atrás de flag + DPA + anonimização (não default).

## Aceite
- [x] Um treino RF-DETR end-to-end (Vast.ai real) gera ONNX servível; registry atualizado (linhagem
      completa: framework/r2_onnx_key/dataset_version_id); sem envio a terceiro por padrão (gate por
      flag explícita, ver Status).
- [ ] Fallback **local** gera ONNX servível — **NÃO satisfeito**: `LocalProvider` é simulação pura
      (nenhum artefato real). Decisão sobre investir nisso retornada para aprovação humana (ADR-0049).

## Checkpoint
- STOP-for-review (fluxo de treino).

## Status (2026-07-15)

**Investigação C-04 — o que já existia (não regravado):**

- `training/vast/remote_train.py`: `train_rfdetr()`/`train_yolox()` reais (RF-DETR Apache via
  `pip install rfdetr`), `model.export()` pra ONNX, validação real com
  `onnxruntime.InferenceSession.run()`. Roda remotamente na Vast.ai (script embutido via heredoc no
  `onstart` da instância — sem acesso ao repo).
- `services/api/app/infrastructure/queue/tasks/training.py::_run_vast_remote_training` +
  `_watch_vast_job`: dispatch REST real fechado ponta a ponta (presigned URLs → instância Vast.ai →
  callback de progresso → polling de status → `INSERT INTO trained_models` → `destroy_instance`
  sempre em `finally`). Não é mock — já validado em produção.
- `services/api/app/infrastructure/gpu/training_compute.py` (ADR-0039): abstração `TrainingCompute`
  com `VastAiProvider`/`LocalProvider`/`EdgeProvider` (este último corretamente marcado
  BLOQUEADO-HARDWARE no próprio docstring).
- Testes reais cobrindo o ciclo: `test_dispatch_vast_real.py`, `test_training_dispatch_task.py`,
  `test_training_compute.py` — mock de rede/DB, mas exercitam a lógica de dispatch de verdade.

**Gaps reais encontrados e FECHADOS nesta task** (código + testes, ver PR):

1. Ultralytics Hub e o fluxo legado Vast+Roboflow (`provision_and_train.sh`) disparavam só por env
   var estar setada no processo — sem opt-in por tenant, violando o espírito do ADR-0047 ("SaaS de
   terceiro nunca é default"). Fechado com feature flag por tenant
   `training_third_party_cloud_enabled` (fail-safe: erro de leitura bloqueia, nunca libera).
2. `INSERT INTO trained_models` não propagava `framework`/`r2_onnx_key`/`dataset_version_id` (colunas
   existentes desde a migration 098) — linhagem incompleta mesmo em treinos reais via Vast.ai. Fechado.
3. Modelos `origin == "simulated"` disparavam `evaluate_challenger_model` automaticamente, entrando na
   avaliação campeão×desafiante como se fossem candidatos reais (ADR-0017: fallback silencioso).
   Fechado: trigger pulado explicitamente pra origin simulado.

**Gap real encontrado e NÃO fechado (decisão pendente, ver ADR-0049):**

`LocalProvider`/`_simulate_training` é simulação pura (lida linha a linha): `time.sleep` + métricas
fake por fórmula, zero dataset baixado, zero chamada a rfdetr/yolox/onnxruntime, zero artefato
`.onnx`/`.pth` real. É o fallback padrão pra qualquer tenant sem chave Vast.ai configurada. Corrigir
"de verdade" exige trazer `torch`/`rfdetr` (dependências pesadas de treino) pro worker Celery, que
hoje não tem GPU nem essas libs — decisão de custo/infra retornada pra aprovação humana em vez de
implementada unilateralmente (mesma disciplina da task-085/ADR-0048). Detalhes e alternativas em
`docs/decisions/adr/0049-treino-rfdetr-gaps-fechados-fallback-local-pendente.md`.

**Legado identificado, não removido nesta task:** `training/vast/train_rfdetr.py` +
`train_yolox.py` + `upload_and_register.py` (usados só por `provision_and_train.sh`, agora atrás do
mesmo flag gate) registram em `models`, não em `trained_models` (o registry canônico) — dois
registries desalinhados coexistindo nesse caminho legado. Não removido/consolidado nesta task por não
ser bloqueante (caminho já gated, uso real hoje é nulo em produção — requer opt-in explícito +
`vastai` CLI/SSH configurados manualmente); registrado aqui como débito conhecido.
