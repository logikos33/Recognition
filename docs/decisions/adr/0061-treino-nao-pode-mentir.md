# ADR-0061 — Treino não pode mentir: simulação e Hub deletados, artefato sempre verificado, gate de licença estendido

**Status:** Proposta — implementado e testado nesta task (branch `claude/treino-honesto`); aguardando
aprovação humana antes de merge/deploy. · **Data:** 2026-08-10 · **Autores:** Vitor Emanuel (Logikos) —
implementação por sessão Claude Code
**Relaciona:** ADR-0060 (supersede parcialmente — ver seção "Relação com a ADR-0060"), ADR-0049 (decisão
pendente que a 0060 já fechava), ADR-0047 (opt-in de nuvem de terceiro, preservado), ADR-0043 (zero AGPL
no serving), ADR-0031 (Training Studio / trained_models como registry canônico), ADR-0017 (fail-loud,
nunca fallback silencioso)

## Contexto

A ADR-0060 (2026-08-04) já tinha resolvido a primeira metade do problema: simulação e o dispatch real ao
Vast.ai passaram a exigir opt-in explícito por tenant, em vez de fallback silencioso. Mas duas categorias
de mentira sobreviveram a essa mudança:

1. **Simulação e Ultralytics Hub continuavam existindo no código**, só atrás de uma flag. Um bug de
   dispatch, uma env var setada por engano em produção, ou um tenant configurado incorretamente ainda
   podiam produzir um "modelo treinado" que nunca foi treinado de verdade — a ADR-0060 tornou isso menos
   provável, não impossível. O fluxo legado Vast+Roboflow (`_dispatch_vast_ai_legacy`,
   `provision_and_train.sh`) também sobrevivia no módulo "pra uso futuro", mesmo depois de já não ser
   mais auto-invocado — treinava no dataset PÚBLICO do Roboflow (Hard Hat Workers, CC BY 4.0), nunca no
   dataset do tenant que disparou o job.
2. **Nenhum caminho confirmava que o artefato existia de verdade antes de marcar um job `completed`.**
   Um provider podia relatar sucesso (Hub com export que falhou silenciosamente, GPU remota com upload
   que não completou, callback adulterado) e o registry (`trained_models`) ganhava uma linha apontando
   pra um objeto que não existe no R2 — indistinguível de um modelo real até alguém tentar ativá-lo em
   produção e descobrir que o arquivo não existe.

Achados adicionais durante a auditoria desta task:
- `POST /api/v1/dashboard/training-metrics` aceitava `model_name` livre de qualquer usuário autenticado
  (inclusive `operator`) — sem checar role nem se o modelo existia de fato, qualquer um fabricava curvas
  de treino fictícias pro dashboard.
- Qualidade (`quality/routes.py::activate_model`) ativava qualquer `quality_training_jobs` existente pro
  módulo Qualidade, **independente do status** — um job `queued`/`running`/`failed` podia ser atribuído a
  câmeras como se fosse um modelo pronto.
- O import `run_quality_training` em dois pontos de `quality/routes.py` estava quebrado — a função real
  se chama `run_quality_training_pipeline`; o retreino de Qualidade via essas duas rotas nunca funcionou
  (`ImportError` em runtime, mascarado pelo `except Exception` genérico do handler).
- O scanner de licença (`scripts/check_license_gate.py`) só varria `services/api/app` e
  `services/inference/inference` por imports AGPL — `training/` e `scripts/` (onde o fluxo legado
  Roboflow vivia) nunca foram escaneados.

## Decisão

1. **Simulação deletada de vez.** `_simulate_training` (training.py), `LocalProvider`
   (training_compute.py), `simulation_explicitly_enabled()`/`TRAINING_SIMULATION_ENABLED` — removidos.
   `GpuProvider.LOCAL` continua existindo no enum (linhagem de dados legados), mas não tem mais nenhum
   provider por trás: um tenant configurado com `training_compute_target='local'` recebe erro alto e
   legível ("treino local não suportado"), nunca uma simulação.
2. **Ultralytics Hub deletado de vez.** `_dispatch_hub` (training.py), `app/infrastructure/hub/` inteiro
   (`ultralytics_hub.py`), `ULTRALYTICS_HUB_API_KEY`/`ULTRALYTICS_HUB_PROJECT_ID` (config.py), e o check
   dessa env em `gpu_enabled` (job_handlers.py) — removidos. `VAST_API_KEY`/`VAST_AI_API_KEY` preservados
   (saem em outro PR, se saírem).
3. **Fluxo legado Vast+Roboflow deletado de vez.** `_dispatch_vast_ai_legacy` (training.py) e os scripts
   que ele invocava — `training/vast/provision_and_train.sh`, `train_rfdetr.py`, `train_yolox.py`,
   `upload_and_register.py` (órfão depois da deleção do script que o chamava) — removidos.
   `training/vast/remote_train.py` (o executor honesto, dataset real do tenant via presigned URL,
   RF-DETR/YOLOX Apache 2.0) e seu test suite **preservados** — é o único caminho de dispatch remoto que
   sobra, coberto por CI (`.github/workflows/ci.yml:210`).
4. **`requirements/training.in`/`training.txt` (ultralytics==8.4.95 pinado) deletados.** Nenhum
   requirements do repo referencia `ultralytics` — o único uso restante era o fluxo legado deletado no
   item 3. `scripts/check_license_gate.py` ajustado (removida a exclusão órfã).
5. **Regra "nunca completed sem artefato verificável".** Novo helper único,
   `app.infrastructure.storage.verify_model_artifact(tenant_id, r2_key) -> bool` — HEAD/exists real no
   storage (R2 ou local, conforme `get_storage`). Aplicado em TRÊS pontos que podem persistir sucesso:
   - `tasks/training.py::dispatch_training`, antes do INSERT em `trained_models`;
   - `tasks/training.py::_watch_vast_job`, antes de repassar `completed` pra `dispatch_training` (defesa
     em profundidade — reconfirma mesmo que `training_jobs.status` já diga `completed`);
   - `job_handlers.py::training_progress_callback_handler`, antes de persistir o status vindo da GPU
     remota — o ponto mais crítico, porque é a ÚNICA verificação que existia zero vezes antes desta task
     (o callback de uma instância Vast.ai, um processo fora do nosso controle direto, era escrito direto
     no banco sem nenhuma confirmação independente).

   Artefato ausente/inacessível (objeto não existe, credencial inválida, storage fora do ar) → o job é
   marcado `failed` com motivo legível, nunca `completed` com um artefato fantasma. Chave R2 determinística
   centralizada em `vast_onnx_artifact_key(tenant_id, job_id)` — nunca duplicada como f-string solta.
6. **Guarda em `POST /api/v1/dashboard/training-metrics`.** `@require_training_role("write")` (registry
   canônico de `app/core/permissions.py` — superadmin/admin/trainer, ou override; operator/analyst/viewer
   bloqueados) + `model_name` precisa corresponder a um `trained_models.name` real do tenant, senão `404`
   (C-01 — nunca `403`, não revela se o nome existe fora do tenant).
7. **Guarda em `POST /api/v1/quality/training/models/<id>/activate`.** Só ativa job com
   `status='completed'` — outro status → `404`. Import quebrado (`run_quality_training` →
   `run_quality_training_pipeline`) corrigido nas duas rotas que disparam retreino de Qualidade.
8. **`scripts/check_license_gate.py::SERVING_SOURCE_DIRS` estendido** para `training/` e `scripts/` —
   antes só cobria o caminho servido; o scan de imports AGPL passa a cobrir também o código de treino em
   si e o tooling do repo.
9. **Manifesto de pesos** (`docs/WEIGHTS_LICENSES.md`) — SAM ViT-B e GroundingDINO (Apache 2.0, já
   hospedados no R2 de produção) com `sha256` verificado por download direto do bucket; DINOv2 marcado
   `PENDENTE` (checkpoint exato a pinar no PR da propagação); DINOv3 **VETADO** (licença custom Meta,
   histórico de litígio); nota sobre o `cc_torch` do SAM2 ser CC BY-NC (não empacotar).

## Relação com a ADR-0060

Esta ADR **não reverte** a ADR-0060 — ela vai além. A 0060 resolveu "simulação/Vast.ai não disparam sem
opt-in"; esta resolve "simulação/Hub/legado não existem mais no código, e nada vira `completed` sem
confirmação de artefato real". Onde a 0060 documentava `_simulate_training`/`LocalProvider`/`_dispatch_hub`
como comportamento existente atrás de flag, esta ADR os declara **removidos**; os trechos correspondentes
da 0060 ficam historicamente corretos para o período em que valeram, mas não descrevem mais o código atual.

## Consequências

- **Positivo:** impossível, por config ou bug, um tenant receber um "modelo" sem nenhum artefato real por
  trás — a barreira não é mais "flag desligada por padrão", é "o código que produzia o fake não existe
  mais" (simulação/Hub) ou "o resultado é sempre reconferido no storage antes de virar `completed`"
  (Vast.ai real). Qualidade não ativa mais treinos incompletos/falhos pra câmeras de produção. Curvas de
  treino no dashboard não podem mais ser fabricadas por qualquer usuário autenticado.
- **Operacional:** nenhuma migration nova. Nenhuma env variável nova exigida — `verify_model_artifact`
  reusa a resolução de storage já existente (`get_storage`/`ALLOW_EPHEMERAL_STORAGE`). Testes que
  mockavam `_simulate_training`/`_dispatch_hub`/`_dispatch_vast_ai_legacy`/`LocalProvider` foram
  removidos ou reescritos para os pontos de extensão que restaram (`get_training_compute`,
  `verify_model_artifact`).
- **Dívida aberta:** DINOv2 sem checkpoint pinado (bloqueia o PR da propagação de anotação, não este).
  `Framework.ULTRALYTICS` (enum) mantido — `domain/detectors/factory.py` ainda trata explicitamente
  linhas legadas de `trained_models` com esse valor (ADR-0043), nenhuma linha nova pode ser criada com
  ele desde que o backend de serving `ultralytics` foi removido, mas o valor do enum documenta a
  linhagem histórica em vez de inventar um estado novo pra dados existentes.

## Testes

`services/api/tests/unit/infrastructure/test_training_dispatch_task.py`,
`test_dispatch_vast_real.py`, `test_training_compute.py`,
`services/api/tests/unit/api/test_training_progress_callback_artifact_guard.py` (novo),
`services/api/tests/unit/api/test_quality_activate_model_guard.py` (novo),
`services/api/tests/integration/test_dashboard_edge_routes.py`,
`services/api/tests/unit/test_license_gate_import_scan.py`.
