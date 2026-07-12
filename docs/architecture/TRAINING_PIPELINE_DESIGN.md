# Training Pipeline — Design de Backend (MLOps Flywheel)

**Referenciado por:** ADR-0031 (Training Studio — ciclo de vida de modelo), ADR-0037 (contrato de API),
ADR-0032 (geometria/config de modelo), ADR-0034 (NVR/DVR), ADR-0035 (feature flags por tenant).

**Nota de nomenclatura:** ADR-0031 referencia este documento como "flywheel 11 estágios", mas a seção
"Estágios do Training Studio" daquele ADR enumera efetivamente **7 estágios** (DADOS → CLASSES →
ANOTAÇÃO → DATASET → TREINAR → AVALIAR/COMPARAR → PROMOVER/IMPLANTAR). Este documento descreve os 7
estágios reais e onde cada um está implementado no backend — não inventa 4 estágios adicionais pra
bater com o número citado; a discrepância no ADR-0031 é anterior a este PR e fica registrada aqui pra
não ser redescoberta como "documentação incompleta" depois.

## Objetivo

Fechar o ciclo completo de MLOps do produto: cada tenant treina, avalia, implanta e monitora o próprio
modelo a partir dos próprios dados — não apenas "escolhe um modelo pronto". Este documento mapeia os 7
estágios do Training Studio (design, ADR-0031) para sua implementação real de backend, construída em 4
PRs stacked (`feat/tp1-schema-port-fixes` → `feat/tp2-ingestion-training` → `feat/tp3-flywheel` →
`feat/tp4-eval-deploy-drift`).

## Os 7 estágios → implementação

| # | Estágio (ADR-0031) | Fonte de dados / mecanismo | Implementado em | Contrato |
|---|---|---|---|---|
| 1 | **DADOS** | (a) captura automática de alertas (WS-B3), (b) NVR/DVR (WS-B1), (c) upload manual (WS-A2), (d) extração de frames de vídeo (pré-existente) + fila de active learning (WS-B2) | PR-1/2 (upload/vídeo), PR-3 (NVR, auto-captura, active learning) | ADR-0037 §upload, §recorders, §active learning |
| 2 | **CLASSES** | `yolo_classes` escopado por tenant+módulo | PR-1 (migration 093) | ADR-0037 §classes |
| 3 | **ANOTAÇÃO** | `AnnotationInterface` + pré-anotação plugável (backend desacoplado, flag OFF por padrão) | PR-2 (anotação), PR-3 (pré-anotação, WS-B4) | ADR-0037 §pré-anotação, ADR-0031 adendo |
| 4 | **DATASET (versão)** | snapshot imutável COCO por split (train/val/test), linhagem completa | PR-1/2 (`dataset_versions`, `build_dataset_version_v2`) | ADR-0037 §datasets |
| 5 | **TREINAR** | job a partir de uma dataset_version; dispatch Vast.ai real → Ultralytics Hub → simulação | PR-2 (`training_jobs`, `dispatch_training`) | ADR-0037 §treinamento, ADR-0038 |
| 6 | **AVALIAR / COMPARAR** | avaliação campeão×desafiante (IoU greedy matching por classe, matriz de confusão cruzando classes) | **PR-4 (WS-C1)** | ADR-0037 §avaliação campeão×desafiante |
| 7 | **PROMOVER / IMPLANTAR** | ativação com gate de eval + atribuição por câmera/módulo com geometria (roi/line/classes/thresholds) + rollback | PR-2 (`activate`), **PR-4 (WS-C2, deploy/model-config)** | ADR-0037 §registry, §deploy/model-config |

## Pós-implantação: monitoramento contínuo (não é um dos 7 estágios do design, mas fecha o flywheel)

**Drift monitor (WS-C3, PR-4):** Celery beat diário compara o sinal de confiança/distribuição de
classes da inferência ao vivo contra o baseline de cada par modelo×câmera, alimentando
`model_drift_metrics`. Quando o drift excede o limiar configurável, nudge best-effort no check de
auto-retreino existente (`check_auto_retraining`) — fechando o ciclo "o modelo foi implantado → está
degradando? → retreinar automaticamente" sem intervenção manual. Ver ADR-0037 §drift monitor pra a
limitação documentada do sinal (só cobre frames com violação, não o universo completo de inferências).

## Permissões (WS-D, todos os estágios)

`training:write` (self-service: rotular, versionar, treinar, comparar) vs `training:approve`
(promover/ativar, deploy/model-config, rollback) — fonte de verdade única em
`app/core/permissions.py`, nunca duplicada nos decorators. Ver ADR-0037 §permissões.

## Onde estão os dados reais (schema)

Ver `docs/DATABASE.md` — tabelas relevantes por estágio: `training_frames`/`yolo_classes` (1-2),
`frame_annotations` (3), `dataset_versions` (4), `training_jobs` (5), `trained_models`/
`model_evaluations` (6), `model_deployments` (7), `model_drift_metrics` (monitoramento contínuo).
