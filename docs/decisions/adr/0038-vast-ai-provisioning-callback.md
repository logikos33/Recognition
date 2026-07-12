# ADR-0038 — Provisioning Vast.ai real: dispatch, callback e fallback

**Status:** Aceita (2026-07-11) · **Relaciona:** ADR-0037 (contrato de API), runbook
`TRAINING_PIPELINE_WEEKEND_MVP.md`. **Implementado em:** PR-2 (`feat/tp2-ingestion-training`, WS-A4).

## Contexto

O fallback de treino em `tasks/training.py` (`_dispatch_vast_ai`) era simulação (log de warning,
nunca executava SSH real). O plano exigia dispatch REST real via `console.vast.ai/api/v0`, com
provisioning, callback de progresso e destruição garantida da instância (GPU paga).

## Decisão

### Cadeia de resolução do dispatch

1. `_get_vast_context(job_id)`: resolve tenant, `dataset_version.coco_r2_key` e API key
   (`resolve_vast_api_key` — integration store do tenant → fallback `VAST_API_KEY` de ambiente).
   Sem contexto completo → `None`.
2. Contexto presente → `_run_vast_remote_training` (fluxo REST real). Ausente →
   `_dispatch_vast_ai_legacy` (script `provision_and_train.sh`, preservado) → sem o script,
   `_simulate_training` (comportamento since sempre, provado pelos testes do PR-1).

### Fluxo REST real

- `callback_token` por-job (`secrets.token_urlsafe(48)`), gravado em `training_jobs.callback_token`,
  revogado (`NULL`) ao final (sucesso, erro ou stop).
- Presigned GET do dataset COCO (`generate_presigned_download_url`, TTL 6h) + presigned PUT dos
  artefatos ONNX/pesos/métricas (TTL 8h).
- `remote_train.py` embutido no `onstart` via heredoc (a instância Vast **não** tem acesso ao
  repositório) — self-contained: `pip install rfdetr|yolox` em runtime, treina, exporta ONNX, valida
  com `onnxruntime`, sobe artefatos, POSTa progresso a cada época e o resultado final.
- `_watch_vast_job`: watchdog que faz *poll* do `training_jobs.status` e da instância a cada
  `VAST_POLL_INTERVAL_SECONDS` (default 60s) até timeout (`VAST_TIMEOUT_SECONDS`, default 7200s) —
  o progresso real chega via callback (não pelo poll); o poll só detecta instância morta/timeout.
- **Destruição garantida**: `client.destroy_instance(...)` em `finally`, sempre — sucesso, erro ou
  exceção do watchdog. Nunca vaza GPU paga.

### Callback de progresso

`POST /api/v1/training/jobs/<id>/progress-callback` — **sem JWT** (a instância remota não tem
identidade de usuário). Autenticação: header `X-Callback-Token` comparado em tempo constante
(`hmac.compare_digest`) contra `training_jobs.callback_token`. Validação de payload (`progress`
0–100, `epoch` inteiro ≥0, `metrics` objeto, `error_message` ≤500 chars). Rate limit 60/min por IP
(sem identidade de tenant nesta rota). Canal Redis de publicação: `training_progress:{job_id}`
(existente — **não** `training:{job_id}`, para não duplicar o registro do modelo feito pelo
fluxo Celery).

### Stop não deixa vazar uma segunda instância GPU (correção pós-revisão adversarial)

Achado crítico: sem tratamento especial, um `stop_job_handler` concorrente ao dispatch em execução
era absorvido como falha genérica → `dispatch_training` marcava `failed` (sobrescrevendo `stopped`) e
o Celery reagendava (`max_retries=1`), provisionando uma **segunda** instância paga para um job já
cancelado. Três camadas de defesa, todas necessárias:

1. `_JobStoppedError` (subclasse de `RuntimeError`): levantada por `_watch_vast_job` quando o status
   observado é `stopped` (distinto de `failed`, que continua sendo genérico/retriable).
2. `update_job()` nunca sobrescreve `status='stopped'` (`WHERE id=%s AND status != 'stopped'`) —
   fecha a race em que `update_fn("running", ...)` roda entre o início do dispatch e o provisioning.
3. `_run_vast_remote_training` recheca `training_jobs.status` imediatamente antes de
   `client.create_instance(...)` e aborta com `_JobStoppedError` sem provisionar nada se já `stopped`.
4. `dispatch_training` captura `_JobStoppedError` separadamente e **nunca** chama `self.retry()`
   para ele — apenas retorna `{"status": "stopped"}`. Falhas reais de infraestrutura continuam
   reagendando normalmente.

### Métricas por-época (RF-DETR)

O callback por-época enviava só o log daquela época; frameworks de treino nem sempre repetem toda
chave a cada época (ex.: mAP calculado a cada N épocas). Como o backend faz `UPDATE ... SET
metrics = %s` (overwrite, não merge JSONB), uma chave só reportada em época anterior desaparecia do
progresso ao vivo. Fix: `remote_train.py` acumula (`last_metrics.update(...)`) e envia o dicionário
acumulado em cada callback, não só o delta da época.

## Pendências (deferred, sem bloquear)

- `VAST_API_KEY` não configurada no ambiente de desenvolvimento → dispatch real pronto, não
  exercitado E2E; fallback de simulação cobre o caminho feliz nos testes.
- `_dispatch_vast_ai` ainda ignora fine-tuning de preço por tenant além do price-cap global
  (`VAST_PRICE_CAP`).
- `upload_and_register.py` (script legado do fluxo `provision_and_train.sh`) segue usando
  `TEST_TENANT_ID` internamente — só o registro real via callback (`_run_vast_remote_training`) usa
  o tenant correto do job.

## Consequências

- Nenhuma GPU paga é provisionada para um job já cancelado pelo usuário — verificado por 3 testes
  dedicados (`test_dispatch_vast_real.py::TestRunVastRemoteTrainingStopRace`,
  `TestDispatchTrainingStopHandling`).
- O canal de progresso (`training_progress:{job_id}`) é o único ponto de registro do modelo treinado
  — reforçado pela guarda anti-duplicação (`get_model_by_job_id`, ADR/ajuste #2 do PR-1) em ambos os
  fluxos que podem chegar lá (Celery direto e bridge Redis→SocketIO).
