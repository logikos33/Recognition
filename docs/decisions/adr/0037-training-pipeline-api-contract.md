# ADR-0037 — Contrato de API da pipeline de treinamento (classes, upload, datasets, registry, inferência)

**Status:** Aceita (2026-07-11) · **Estende:** ADR-0031 (training studio model lifecycle) ·
**Implementado em:** PR-1 (`feat/tp1-schema-port-fixes`, migrations 093-101 + camada de dados),
PR-2 (`feat/tp2-ingestion-training`, Fase A — endpoints deste ADR), PR-3 (`feat/tp3-flywheel`,
Fase B — WS-B1..B4: recorders/NVR, active learning, auto-captura, pré-anotação) e PR-4
(`feat/tp4-eval-deploy-drift`, WS-C1..C4: avaliação campeão×desafiante, deploy/model-config por
câmera, drift monitor, docs).

## Contexto

O plano `.claude-plan-training-pipeline.md` e a crítica arquitetural definiram o modelo de dados e os
workstreams (WS-A1..A6) da Fase A. Este ADR é o **mapa do contrato** hand-off para o frontend
(redesenhado à parte) consumir — o QUÊ dos endpoints (request/response, campos), sem nenhuma decisão
visual. Envelope de resposta em toda a API: `{"success": bool, "data"?: ..., "error"?: str}` (ver
`app/core/responses.py` — a documentação legada de `{"status": "success"|"error"}` está desatualizada;
o formato real usado em toda a base é `success`/`error`).

## Decisão

### Permissões (WS-D)

Dois níveis, aplicados via `@require_training_role("write"|"approve")` (sempre após `@jwt_required()`):

| Nível | Ações | Roles com bypass automático | Fonte |
|---|---|---|---|
| `write` | criar/rotular/versionar/treinar/upload | `superadmin`, `admin`, `trainer` | `default_roles_for("training:write")` |
| `approve` | activate/deploy/rollback | `superadmin` (exclusivo) | `default_roles_for("training:approve")` |

Fora desses roles, um override `allow=true` em `public.user_permission_overrides` (escopo do tenant do
JWT) concede acesso pontual por usuário. A fonte de verdade é o registry canônico
`app/core/permissions.py` (pré-existente, WS7) — **não** um tuple hardcoded no decorator, para não
divergir de outras superfícies que já consultam o mesmo registry.

### Classes (WS-A1)

| Método | Path | Nível | Request | Response (200) |
|---|---|---|---|---|
| GET | `/api/classes?module=epi&include_counts=false` | leitura | — | `{"success":true,"classes":[{id,name,color,tenant_id,module_code,annotation_count?}]}` (envelope legado do AnnotationInterface.jsx preservado) |
| POST | `/api/classes` | write | `{name, color?, module?}` | `201 {"success":true,"data":{classe}}` |
| PUT | `/api/classes/<int:class_id>` | write | `{name?, color?}` (≥1 campo) | `200 {"success":true,"data":{classe}}` \| `404` outro tenant \| `409` nome duplicado |
| DELETE | `/api/classes/<int:class_id>` | write | — | `200 {"success":true,"data":{"deleted":true,"id":N}}` \| `404` \| `409` (N anotações vinculadas) |

**Pendência conhecida** (não corrigida — requer migration com `DROP CONSTRAINT`, proibido pela política
deste projeto sem decisão humana explícita): a constraint real é `UNIQUE(user_id, name)` — nunca
estendida com `module_code` quando a migration 093 adicionou escopo por módulo. Um usuário não pode
reusar o mesmo nome de classe em dois módulos diferentes (ex.: "helmet" em `epi` e em `quality`).

### Upload de imagens (WS-A2)

| Método | Path | Nível | Request | Response |
|---|---|---|---|---|
| POST | `/api/training/images/upload` | write | multipart `files[]` | `{"success":true,"data":{"uploaded":N,"failed":N}}` |
| GET | `/api/training/images?source=&status=&page=` | leitura | — | paginado; `source∈{video,upload,auto,nvr}`, `status` computado (`unlabeled`\|`labeled`\|`reviewed`) — sem coluna nova |

### Datasets (WS-A3)

| Método | Path | Nível | Request | Response |
|---|---|---|---|---|
| GET/POST | `/api/v1/datasets` | leitura/write | POST: `{name, description?}` | dataset pai (tenant+module scoped) |
| POST | `/api/v1/datasets/<id>/versions` | write | `{name?, split{train,val,test}, augmentations?, format}` | dispara `build_dataset_version_v2` (Celery, queue `versioning`) — snapshot COCO com linhagem completa |
| GET | `/api/v1/dataset-versions/<id>` | leitura | — | detalhe + presigned GET do COCO |

### Treinamento (WS-A4)

| Método | Path | Nível | Notas |
|---|---|---|---|
| POST | `/api/training/jobs` | write | `{dataset_version_id, framework, base_model, hyperparams}` (estendido — campos legados continuam funcionando) |
| GET | `/api/training/jobs/<id>/status` \| `/progress` | leitura | `/progress` lê Redis (`training_progress:{job_id}`), sem bater no banco |
| POST | `/api/training/jobs/<id>/stop` | write | marca `stopped`, revoga `callback_token`, destrói instância GPU (best-effort) |
| POST | `/api/v1/training/jobs/<id>/progress-callback` | **interno, sem JWT** | header `X-Callback-Token` (comparação `hmac.compare_digest` contra `training_jobs.callback_token`); rate limit 60/min por IP — ver ADR-0038 |

### Registry de modelos (WS-A5)

| Método | Path | Nível | Notas |
|---|---|---|---|
| GET | `/api/v1/models?module=&status=` | leitura | lista tenant-scoped |
| GET | `/api/v1/models/<id>` | leitura | linhagem expandida: `dataset_version → job → model → deployments` |
| POST | `/api/v1/models/<id>/activate` | approve | gate de eval (`verdict=reject` → `409` a menos que `force=true` **e** role admin+); sincroniza `{schema}.models` via `ModelRolloutRepository.pin_model` best-effort |
| GET | `/api/v1/models/<id>/eval` \| `/drift` | leitura | última avaliação / janelas de drift |

`GET /api/training/models` (legado) permanece — deprecar via header `Deprecation` fica para o PR-3
(WS-E), junto do ADR de contrato correspondente se a migração de fato acontecer.

### Inferência por câmera (WS-A6)

Sem endpoint novo — mudança interna de `tasks/inference.py`: resolução do modelo efetivo em cascata
(`model_deployments` ativo → `cameras.model_epi_id` → `trained_models.r2_onnx_key` → cache local),
fallback 100% preservado para `DETECTOR_BACKEND`/`DETECTOR_MODEL_PATH` quando não há deployment
configurado — nenhuma câmera existente muda de comportamento sem migração explícita para o novo fluxo.

### Recorders / NVR-DVR (WS-B1, ADR-0034) — PR-3

| Método | Path | Nível | Notas |
|---|---|---|---|
| GET | `/api/v1/recorders` | leitura | lista tenant-scoped, senha nunca no payload |
| POST | `/api/v1/recorders` | write | cria; `password` opcional, cifrado Fernet(`CAMERA_SECRET_KEY`) antes de persistir |
| GET | `/api/v1/recorders/<id>` | leitura | 404 se de outro tenant |
| PUT | `/api/v1/recorders/<id>` | write | `password` recifra; demais campos allowlist (`RecorderRepository._UPDATABLE_FIELDS`) |
| DELETE | `/api/v1/recorders/<id>` | write | |
| POST | `/api/v1/recorders/<id>/test` | write | cascata ONVIF Profile G → Hikvision ISAPI → RTSP genérico; grava `status`/`last_error`/`last_tested_at` |
| GET | `/api/v1/recorders/<id>/recordings?channel=&from=&to=` | leitura | timeline de gravações existentes no intervalo; `502` se o gravador não responder |
| POST | `/api/v1/recorders/<id>/extract-frames` | write | body `{channel, from, to, interval_seconds?, module_code?}`; dispara Celery (`queue=extraction`), `202` + `task_id` |

**Pendência explícita**: nenhum client (ONVIF/ISAPI/RTSP) foi validado contra hardware real — sem
NVR/DVR disponível neste ambiente de desenvolvimento. Cobertura via protocolo mockado (SOAP/XML/HTTP
com fixtures realistas). Validar contra um gravador real antes de depender disso em produção.
Dahua/Intelbras caem no fallback RTSP genérico (sem busca de timeline real) — as APIs HTTP próprias
desses fabricantes não foram implementadas nesta PR.

### Active learning queue (WS-B2, ADR-0031)

| Método | Path | Nível | Notas |
|---|---|---|---|
| GET | `/api/training/active-learning/queue?module=&limit=` | leitura | frames não rotulados ordenados por `model_confidence ASC NULLS LAST` |

Sinal de incerteza é `training_frames.model_confidence` (populado pela inferência ao vivo em frames
`source='auto'`, WS-B3) — **não** depende de `uncertainty_score`/pré-anotação (WS-B4, flag OFF por
padrão). Frames sem `model_confidence` (upload manual) ficam no fim da fila.

### Auto-captura (WS-B3) — sem endpoint novo

Hook único em `tasks/inference.py::_save_alert` (nunca duplicar em `socket_bridge.py::
_create_alert_and_verify` — caminho concorrente que já insere em `alerts` direto por SQL cru, sem
coordenação com o worker). Rate-limit atômico via Redis (`INCR`+`EXPIRE`, teto configurável por
tenant via `feature_flags.auto_capture_daily_cap`, default 20/câmera/dia). Feature flag
`auto_capture_enabled` (default **true** — custo marginal, reusa o frame já decodificado pro alerta).

### Pré-anotação plugável (WS-B4) — ADR-0031, adendo 2026-07-12

| Método | Path | Nível | Notas |
|---|---|---|---|
| POST | `/api/training/frames/<id>/pre-annotate` | write | `403` se `feature_flags.pre_annotation_enabled` estiver OFF (default) |
| POST | `/api/training/frames/<id>/accept-suggestions` | write | body opcional `{"indices": [0,2]}`; sem body aceita todas as sugestões pendentes |

Backend plugável (`PreAnnotationBackend`), OFF por padrão — DINO+SAM (`DinoSamHttpBackend`) disponível
como opção via `feature_flags.pre_annotation_backend`, não como default. Ver adendo do ADR-0031 para o
histórico (removido em maio/2026 por custo×qualidade) e o candidato a avaliar (Jetson Platform
Services) antes de qualquer tenant ligar a flag de verdade.

### Avaliação campeão×desafiante (WS-C1) — PR-4

| Método | Path | Nível | Notas |
|---|---|---|---|
| POST | `/api/v1/models/<id>/evaluate` | approve | body opcional `{"dataset_version_id": "<uuid>"}` (override); dispara `evaluate_challenger_model` (Celery, `queue=training`), `202` + `task_id` |

A avaliação também é disparada automaticamente (best-effort, nunca falha o job de treino) logo após
um novo `trained_models` ser registrado — nos dois pontos onde isso acontece hoje:
`tasks/training.py::dispatch_training` (fallback Celery) e `socket_bridge.py::_register_trained_model`
(caminho do training-service via Redis pub/sub). Roda o modelo desafiante — e o campeão ativo do
tenant+módulo, se houver — contra o split de holdout (`test`, fallback `val` se `test_count=0`; erro
explícito `no_holdout_split` se os dois forem 0) da `dataset_version` de origem, casando detecções
contra o ground-truth COCO por IMAGEM (IoU greedy matching, `app/domain/services/eval_metrics.py`).
Veredito (`model_evaluations.verdict`, já consumido pelo gate de `POST .../activate`):
`promote` se `map50` do desafiante não cair mais que 1pp abaixo do campeão E nenhuma classe perder
mais que 5pp de recall; sem campeão ativo → `promote` automático. `confusion_matrix` é uma matriz
separada (matching cruzando classes, não só por classe) — diagnóstico de confusão real entre
classes, não usado no cálculo de `map50`.

**Pendência conhecida**: modelos registrados sem `r2_onnx_key`/`dataset_version_id` (ex.: fallback
`dispatch_training` legado, que só grava `model_path`) fazem a avaliação retornar
`{"status":"error","reason":"missing_onnx_key"}` graciosamente — mesmo padrão de
`tasks/model_validation.py::validate_onnx` para o mesmo gap pré-existente.

### Deploy / model-config por câmera (WS-C2) — PR-4

| Método | Path | Nível | Notas |
|---|---|---|---|
| GET | `/api/cameras/<id>/model-config?module=epi` | leitura | deployment ativo da câmera+módulo (`model_deployments`), ou `null` |
| POST | `/api/cameras/<id>/model-config` | approve | body `{model_id, module_code? (default 'epi'), config: {roi?, line?, classes, thresholds?}}`; upsert (desativa o ativo, cria novo — histórico completo preservado) |
| GET | `/api/cameras/<id>/model-config/history?module=` | leitura | todos os deployments da câmera, mais recentes primeiro |
| POST | `/api/cameras/<id>/model-config/rollback` | approve | body `{deployment_id}`; cria um NOVO deployment com o mesmo `model_id`/`config` do alvo (nunca reescreve a linha antiga) |

Registry-level (`model_deployments`, migration 100) — **aditivo** ao Task 045
(`cameras.model_{module}_id`, `model_handlers.py`): o Task 045 é a atribuição simples; este é o lado
com histórico completo, geometria normalizada 0..1 (`roi`: ≥3 pontos, XOR `line`: exatamente 2 pontos),
`classes` habilitadas e `thresholds` por classe (validados em
`app/domain/services/geometry_validation.py`). **Não confundir** `roi`/`line` daqui com
`roi_points`/`line_points` da entidade "Cenário/Operação" do ADR-0032 — schemas e propósitos
diferentes (config de deploy do modelo vs. regra de negócio). A cascata de resolução de modelo pra
inferência ao vivo (`tasks/inference.py::_resolve_camera_model`) já lia `model_deployments` desde o
PR-1 — este PR só adiciona o lado de ESCRITA. Notifica `camera:model_change:{camera_id}` (mesmo canal
Redis do Task 045) para invalidar o detector cacheado do worker.

### Drift monitor (WS-C3) — PR-4, Celery Beat

Sem endpoint novo — `GET /api/v1/models/<id>/drift` (já documentado acima) passa a ter um produtor:
task `compute_drift_metrics` (`tasks/model_drift.py`, beat diário, `queue=training`). Por tenant ativo,
escopado às câmeras que geraram ≥1 alerta na janela do dia UTC anterior; resolve o modelo efetivo via
a MESMA cascata de `_resolve_camera_model`; agrega `avg_confidence` e `class_distribution`
(proporções, não contagens brutas) dos alertas da janela; grava em `model_drift_metrics` com
`drift_score = |Δavg_confidence| + L1(class_distribution)` contra o baseline (primeira janela salva
do par modelo×câmera). Idempotente por janela (`DriftMetricsRepository.exists_for_window`).
`drift_score` acima do limiar (env `DRIFT_SCORE_ALERT_THRESHOLD`, default `0.3`) dispara
`check_auto_retraining.delay()` best-effort (nudge no check horário existente, não uma trigger nova).

**Limitação documentada** (premissa já presente no comentário da migration 101, não é regressão
desta PR): o sinal vem só de `alerts`, que só existe pra frames COM violação
(`_has_violation` em `tasks/inference.py`). Frames 100% conformes são invisíveis ao cálculo — um
tenant com compliance melhorando (menos violações) gera MENOS dado pro drift, não mais confiança no
modelo.

## Consequências

- Front consome exatamente estes contratos; qualquer campo/endpoint adicional exige atualização deste
  ADR antes do merge (regra do plano: "endpoint/campo novo → ADR de contrato").
- A pendência de `yolo_classes` (UNIQUE sem module_code) é uma limitação conhecida do MVP — registrada
  aqui e no código (`tenant_class_service.py`) para não ser redescoberta como bug "novo" depois.
- Bypass de permissão por role deriva do registry canônico, não de um valor duplicado — mudanças de
  `default_roles` em `app/core/permissions.py` refletem automaticamente nos gates de treino.
- `WS-C1..C4` neste ADR referem-se ao escopo do PR-4 (avaliação, deploy, drift, docs) — um comentário
  informal "WS-C4" em `tasks/auto_training.py` (ordem de criação do job antes do dispatch) foi
  renomeado durante o PR-4 pra não colidir com este label.
