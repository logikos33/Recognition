# ADR-0037 — Contrato de API da pipeline de treinamento (classes, upload, datasets, registry, inferência)

**Status:** Aceita (2026-07-11) · **Estende:** ADR-0031 (training studio model lifecycle) ·
**Implementado em:** PR-1 (`feat/tp1-schema-port-fixes`, migrations 093-101 + camada de dados) e
PR-2 (`feat/tp2-ingestion-training`, Fase A — endpoints deste ADR).

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

## Consequências

- Front consome exatamente estes contratos; qualquer campo/endpoint adicional exige atualização deste
  ADR antes do merge (regra do plano: "endpoint/campo novo → ADR de contrato").
- A pendência de `yolo_classes` (UNIQUE sem module_code) é uma limitação conhecida do MVP — registrada
  aqui e no código (`tenant_class_service.py`) para não ser redescoberta como bug "novo" depois.
- Bypass de permissão por role deriva do registry canônico, não de um valor duplicado — mudanças de
  `default_roles` em `app/core/permissions.py` refletem automaticamente nos gates de treino.
