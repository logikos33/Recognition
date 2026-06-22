# AUDITORIA DE QUALIDADE — Recognition EPI Monitor V2
**Data:** 2026-06-21  
**Escopo:** `services/api/` e `apps/frontend/`  
**Gate atual:** ruff ✅ | pytest `--cov-fail-under=30` (11 deselects) | tsc | migrations-harness

---

## P0 — SEGURANÇA CRÍTICA

### P0-01 · Cross-tenant: `get_annotated_by_video` sem filtro de tenant/owner
**Arquivo:** `services/api/app/infrastructure/database/repositories/frame_repository.py:122`  
**Severidade:** P0 — vazamento de dados entre tenants  
**Descrição:** `get_annotated_by_video(video_id)` faz `WHERE tf.video_id = %s AND tf.is_annotated = TRUE` sem verificar ownership do vídeo. Qualquer tenant que conhece um `video_id` de outro tenant pode listar todos os frames anotados do vídeo alheio.  
**Fix proposto:** Adicionar JOIN em `training_videos` e filtrar por `tenant_id`. Seguir a cadeia de callers (route→service→repo) e atualizar assinatura + chamadores. Escrever teste de regressão que FALHA antes e PASSA depois.  
**Esforço:** M (½ dia — mudança de assinatura em cadeia)

### P0-02 · Cross-tenant: `count_validated` filtra por `user_id` não por `tenant_id`
**Arquivo:** `services/api/app/infrastructure/database/repositories/frame_repository.py:164`  
**Severidade:** P0 — pode revelar contagem de frames de tenant errado se user_id for reutilizado  
**Descrição:** `count_validated(video_id, user_id)` junta `training_videos tv` e filtra `tv.user_id = %s`, mas `user_id` em contexto multi-tenant deveria ser `tenant_id`. Se o campo na tabela for `tenant_id`, o filtro pode não estar restringindo corretamente.  
**Fix proposto:** Verificar schema real da coluna em `training_videos`; se a coluna for `tenant_id`, o filtro deve usar `tenant_id`. Manter a semântica admin-override.  
**Esforço:** S (2h)

### P0-03 · Cross-tenant: `alert_repository.list_with_filters` usa f-string com `where` construído
**Arquivo:** `services/api/app/infrastructure/database/repositories/alert_repository.py:108`  
**Severidade:** P0 (potencial) — verificar se `where` inclui sempre `tenant_id`  
**Descrição:** `SELECT COUNT(*) as count FROM alerts a WHERE {where}` — o `where` é construído dinamicamente. Verificar se `tenant_id` está sempre incluído como primeira condição quando o contexto é multi-tenant. Os métodos `list_by_tenant`, `count_by_tenant` filtraram corretamente, mas `list_with_filters` precisa de inspeção.  
**Fix proposto:** Garantir que `tenant_id = %s` é sempre a primeira condição em `list_with_filters`.  
**Esforço:** S (1h)

### P0-04 · Cross-tenant: `annotation_repository` filtra por `user_id` mas não `tenant_id`
**Arquivo:** `services/api/app/infrastructure/database/repositories/annotation_repository.py:26`  
**Severidade:** P0 — `SELECT * FROM yolo_classes WHERE user_id = %s` — em multi-tenant, classes podem cruzar tenants se user_id não for o discriminador certo.  
**Fix proposto:** Verificar se `yolo_classes` tem `tenant_id`; se sim, adicionar filtro. Se o campo for `user_id` na tabela, documentar que é o discriminador correto neste contexto.  
**Esforço:** S (1h)

### P0-05 · Cross-tenant: `counting_repository.get_session` sem filtro tenant
**Arquivo:** `services/api/app/infrastructure/database/repositories/counting_repository.py:28`  
**Severidade:** P0 — `SELECT * FROM counting_sessions WHERE id = %s` — sem filtro de tenant. IDOR: qualquer autenticado pode acessar sessão de outro tenant conhecendo o UUID.  
**Fix proposto:** Adicionar `AND tenant_id = %s` (ou JOIN em cameras para derivar tenant). Verificar se `counting_sessions` tem `tenant_id` na migration.  
**Esforço:** S (2h)

---

## P1 — BUGS E TESTES DESELECIONADOS

### P1-01 · 11 testes deselecionados no CI (causas raiz confirmadas)

| # | Teste | Arquivo | Causa Raiz | Fix |
|---|-------|---------|-----------|-----|
| 1 | `test_invalid_scheme` | `tests/unit/core/test_validators.py:69` | `RTSPUrlValidator.ALLOWED_SCHEMES` foi expandido para incluir `http/https` (Hikvision ISAPI). O teste espera `http://` rejeitar, mas agora é válido. | Trocar URL do teste para `ftp://` ou `telnet://` (ainda inválidos). |
| 2 | `test_upload_file_calls_upload_file` | `tests/unit/infrastructure/test_r2_storage.py` | `R2Storage.upload_file` agora passa `ExtraArgs={"ContentType": content_type}` ao boto3, mas o assert do teste não inclui esse argumento. | Atualizar assert para incluir `ExtraArgs`. |
| 3 | `test_delete_camera_success` | `tests/unit/domain/test_camera_service.py:90` | Mock retorna `{"id": cam_id, "user_id": uid}` mas `delete_camera()` acessa `camera["tenant_id"]` → `KeyError`. | Trocar `"user_id"` por `"tenant_id"` no mock. |
| 4 | `test_delete_camera_wrong_user` | `tests/unit/domain/test_camera_service.py:99` | Mesmo que #3 — mock usa `"user_id"` → `KeyError`. | Idem. |
| 5 | `test_delete_camera_admin_override` | `tests/unit/domain/test_camera_service.py:107` | Mesmo que #3. | Idem. |
| 6 | `test_build_rtsp_url_with_override` | `tests/unit/domain/test_camera_service.py:142` | Mock usa `"user_id"`, serviço acessa `"tenant_id"` → `KeyError`. | Idem. |
| 7 | `test_build_rtsp_url_generated` | `tests/unit/domain/test_camera_service.py:153` | Mesmo que #6. | Idem. |
| 8 | `test_build_rtsp_url_wrong_user_raises` | `tests/unit/domain/test_camera_service.py:179` | Mesmo que #6. | Idem. |
| 9 | `test_create_camera` (repositories) | `tests/unit/infrastructure/test_repositories.py:118` | Test passa `"user_id": uuid4()` mas `CameraRepository.create()` faz `data["tenant_id"]` → `KeyError`. | Trocar `"user_id"` por `"tenant_id"` no dict de entrada. |
| 10 | `test_get_for_camera_returns_video_for_superadmin` | `tests/test_demo_videos.py:231` | Patch `"app.domain.services.demo_video_service._get_repo"` — verificar se `_get_repo` ainda existe com esse nome no módulo atual. | Verificar e atualizar o patch path. |
| 11 | `test_export_pdf_creates_file` | `tests/quality/test_wiser_integration.py:80` | Assinatura de `_export_pdf` alterada; ou `reportlab` não instalado na venv de CI. | Verificar assinatura atual de `_export_pdf` e atualizar a chamada; ou garantir reportlab no requirements. |

**Fix para todos os testes 3–9:** PR único `fix(tests): corrigir mocks user_id→tenant_id e ExtraArgs nos testes deselecionados`, remover 9 dos 11 `--deselect` do `ci.yml`. Testes 1 e 10–11 em PRs próprios (assuntos distintos).

### P1-02 · `_dispatch_vast_ai`: não encontrado (já removido ou renomeado)
**Status:** Verificado — nenhuma ocorrência em `services/api/`. O débito mencionado no CLAUDE.md foi provavelmente removido. Nenhuma ação necessária.

### P1-03 · Cobertura de módulos descobertos
**Arquivos descobertos com cobertura < threshold:**
- `services/api/app/infrastructure/queue/tasks/quality_training.py` (complexo, sem testes dedicados visíveis)
- `services/api/app/domain/services/operations/` (registry + canonicals)
- Módulos `validation_handlers`, `versioning`, `training dispatch` mencionados no CLAUDE.md

---

## P2 — PADRÕES E CODE SMELLS

### P2-01 · `print()` no backend: 47 ocorrências
**Impacto:** Logs não-estruturados, sem nível, sem contexto. P2.  
**Fix:** Substituir por `logging.getLogger(__name__).info/debug/warning`. PRs por módulo.

### P2-02 · Arquivos >200 linhas (excluindo venv)
| Arquivo | Linhas |
|---------|--------|
| `app/api/v1/admin/routes.py` | 2150 |
| `app/api/v1/quality/routes.py` | 2074 |
| `app/api/v1/edge/routes.py` | 781 |
| `app/api/v1/videos/routes.py` | 753 |
| `app/infrastructure/queue/tasks/quality_inference.py` | 735 |
| `app/api/v1/admin/routes_versions.py` | 498 |
| `app/api/v1/quality/gate_service.py` | 608 |
| `app/__init__.py` | 379 |

**Fix:** Extrair blueprints/sub-rotas. P2 — não bloqueia, mas `admin/routes.py` + `quality/routes.py` são riscos de manutenção.

### P2-03 · TypeScript `any`: 29 ocorrências em `apps/frontend/src/`
**Fix:** Substituir por tipos concretos. P2 — trabalho gradual por módulo.

### P2-04 · Raw `fetch()` bypassing `api.ts` wrapper
Ver seção **Contrato Front↔Back** para a lista completa. P1 para os que têm Auth header manual; P2 para os demais.

---

## P3 — INFRA / ALTO RAIO

### P3-01 · eventlet deprecated (gunicorn v26) — ALTO RAIO, needs-human
**Arquivo:** `nixpacks.toml`, `railway_start.py`, requirements  
**Descrição:** gunicorn v26 remove suporte a eventlet. Worker SocketIO usa eventlet. Migração para `gevent` ou `threading` worker muda o modelo de concorrência.  
**Ação:** PR de spike, CI verde + smoke em staging, **parar para validação humana**. Não auto-mergear.

### P3-02 · Schema drift: verificar colunas referenciadas vs schema real
**Ação:** Rodar o harness de migrations (D1 pass1/pass2) para confirmar que todas as colunas usadas no código existem nas migrations. Automatizado no CI.

---

## Resumo por prioridade

| Prioridade | Itens | Status |
|-----------|-------|--------|
| P0 (segurança) | 5 | ⏳ para execução |
| P1 (bugs + 11 testes) | 3 grupos | ⏳ para execução |
| P2 (padrões) | 4 | ⏳ para execução |
| P3 (infra/alto-raio) | 2 | ⏳ needs-human |
