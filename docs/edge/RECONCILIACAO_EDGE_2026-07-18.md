# Reconciliação Edge — planos 2026-07-18 vs. código real (develop tip)

**Data:** 2026-07-18 · **Base:** worktree de `origin/develop` @ `5f0d8c3c` (merge #198, consolidação 2026-07-18)
**Método:** C-04 — cada afirmação dos planos confrontada com o código real (arquivo:linha). `git fetch --all --prune` feito; nenhum ref contém versão diferente.

> **Conclusão de topo:** os planos (`PLANO_CONTROLE_EDGE`, `PLANO_SEGURANCA_EDGE`, ADR-0054) foram escritos em 2026-07-18 **antes** da consolidação #198, que trouxe trabalho (WS7/WS10, task-109/110, commit `71ec7461`) resolvendo **~metade dos achados**. Executar os prompts ao pé da letra reconstruiria coisa já feita. Abaixo, o que é REAL vs. JÁ RESOLVIDO, com evidência.

---

## Trilha de SEGURANÇA

| # | Achado | Veredito | Evidência |
|---|---|---|---|
| **S1** | Escopos de device declarados mas nunca aplicados; não existe `require_scope` | 🔴 **CONFIRMADO** | `core/device_auth.py:104-147` — `get_device_context` verifica `DeviceClaims` mas **descarta `.scopes`**, retorna só `(tenant,site,device)`. `grep require_scope\|has_scope` = zero. Enroll concede **todos** os escopos: `edge/routes.py:622` `_DEFAULT_SCOPES = [s.value for s in DeviceTokenScope]`, ecoado em `:667`. |
| **S2** | `serve_hls` sem checagem de tenant | 🔴 **CONFIRMADO** | `cameras/stream_handlers.py:165` `serve_hls` — sem JWT, valida só UUID + filename (`:172-176`). Sem tenant. (Os checks de tenant em `:346-356` são de `start_stream`, outro handler.) **Decisão de arquitetura pendente.** |
| **S3** | `toggle_module_class` cross-tenant | ✅ **JÁ RESOLVIDO** | `modules/routes.py:81-105` passa `tenant_id`, docstring 404. `module_service.py:223-244` `toggle_class` → `tenant_has_module` falso → `NotFoundError`/404. `module_classes` é catálogo global (sem coluna tenant_id) — isolamento = tenant precisa ter o módulo. |
| **S4** | `/api/streams/status` público, sempre 200 | ⚠️ **CONFIRMADO** | `streams/routes.py:17-18` `@route("/status")` sem decorator de auth; `:23,41,44` sempre `200`. 44 linhas. |
| **S5** | Rotas sem gate de admin | ⚠️ **CONFIRMADO** | `edge_commands/routes.py:115` `list_commands` (`GET /commands`) = JWT+tenant, **sem** `get_role()` admin. `site_gateways/routes.py:74` `update_gateway_status` (`PATCH /status`) sem gate (vs. `upsert_gateway:51` que checa "Acesso restrito a admins"). |
| **B4** | `PATCH /site-gateways/<id>/status` exige JWT de usuário, mas docstring diz "usado pelo edge" | ⚠️ **CONFIRMADO** (contrato) | `site_gateways/routes.py:74-76`. O edge não consegue chamar. Registrar p/ trilha de integração. |
| **S6** | Dois enrollments incompatíveis | ⚠️ **CONFIRMADO** | `devices/routes.py:97-99` `/claim` = **público** (`@limiter.limit`, sem `@jwt_required`), emite JWT HS256 `device_enrollment`. `edge/routes.py:625` `/enroll` = token opaco SHA-256. Nenhum dos dois é consumido pelo frontend (`grep` em `apps/frontend/src` = zero). **Decisão pendente: qual sobrevive.** |
| **S7** | Drift ADR-0019 ↔ implementação | ⚠️ **CONFIRMADO** | `/auth/rotate` inexistente; `/enrollment/redeem` inexistente (só `/enroll`). Device gera o próprio par e auto-assina; `/enroll` devolve só `{tenant,site,device,scopes}` (`:667`). Oposto do ADR. → **corrigir o ADR-0019 para a realidade.** |
| **S8** | Segredo `admin@rvb.com.br` commitado | 🔴 **HERDADO** (ação do Vitor) | Não investigado por shell/SQL (regra: não tocar em credencial). Recomendação: rotacionar **pela aplicação**, avaliar expurgo do histórico. Bloqueante de go-live. |

**Novos achados (fora dos planos — registrar, não corrigir nesta rodada):**
- `API_CONTRACT_MAP.md` item #7: `GET /api/alerts/<alert_id>/snapshot` sem filtro tenant → possível vazamento cross-tenant (P0). Não estava no `PLANO_SEGURANCA`.
- `API_CONTRACT_MAP.md` item #8 está **stale ao contrário**: afirma que `edge_events` ainda passa o objeto `request` — o código já foi corrigido. Corrigir o map.

---

## Trilha de INTEGRAÇÃO (F0–F2)

| # | Achado do plano | Veredito | Evidência |
|---|---|---|---|
| **B1** | `edge_commands` e `edge_events` passam `request` onde a auth espera a string do token → `DecodeError` sempre | ✅ **JÁ RESOLVIDO** | `edge_commands/routes.py:31-39` → `get_device_context(request)` (extrai bearer). Docstring: *"corrige o bug em que o objeto request era passado no lugar do token"*. `edge_events/routes.py:41-59` extrai bearer corretamente. |
| **B2** | Auth fora do `try` em `poll_pending_commands` → 500 em vez de 401 | ✅ **JÁ RESOLVIDO** | `edge_commands/routes.py:76-78` `ctx = _get_device_context(); if not ctx: return error(...,401)`. |
| **B3/A1-doc** | `API_CONTRACT_MAP.md` mente sobre o bug | ⚠️ **PARCIAL** | O map foi reescrito; agora item #8 mente **ao contrário** (diz que edge_events está quebrado). Corrigir. |
| **B5** | `CountingLineOperation` registrada 2× | ✅ **JÁ RESOLVIDO** | `operations/canonical/__init__.py:15-26` — cada operação registrada 1×. |
| **A1** | `GET /edge/config/poll` não existe | ⚠️ **PARCIAL / A COMPLETAR** | **Existe** (`edge/routes.py:215`, commit `71ec7461`), device-auth, escopo site. **MAS** sem `config_version`/`ETag`/`304` e **não reusa o composer** de `scenarios/` (usa `list_for_site_config`). → F1 = adicionar versionamento + reuso do composer. |
| **A2** | `/edge/detections` (uploader) não existe | ⚠️ **CONFIRMADO** | Sem rota `/edge/detections`. `edge-sync-agent/app/uploader.py:45` aponta p/ `/api/v1/edge/detections`. `/events/ingest` existe. **Decisão: canônico.** |
| **A7/F5** | Faltam `attention_points`,`stage_timer`,`crowd_zone`,`dwell_zone` → bloqueia RVB (ADR-0053) | ✅ **JÁ RESOLVIDO** | Todos registrados: `operations/canonical/__init__.py:23-26` (task-109/110). **RVB desbloqueado.** Registry segue estático (tipo novo = deploy) — decisão estático-vs-declarativo permanece, mas não bloqueia RVB. |
| **F2** | `fps_target`/`quality_preset`/`confidence_threshold` sem consumidor de runtime (UI decorativa) | ⚠️ **CONFIRMADO** | `fps_target` só em `cameras/config_handler.py` (write path); **zero** consumidor em `services/inference`. Laço decorativo real. → implementar. |
| **poll** | `_DEFAULT_INTERVAL = 300.0`, sem ETag no cliente | ⚠️ **CONFIRMADO** | `edge-sync-agent/app/config_poller.py:17`. → parte do F1 (lado cliente). |

---

## Re-escopo proposto desta rodada

**Já resolvido (marcar OBSOLETO, não tocar):** B1, B2, B5, S3, A7/F5.
**Executável sem decisão (confirmado):** S1 (prioridade máxima), S4, S5, B4-registro, S7 (corrigir ADR), F1-versionamento+composer, F2-laço decorativo, correção do `API_CONTRACT_MAP`.
**Bloqueado por decisão do Vitor:** S2 (abordagem HLS), S6 (qual enrollment sobrevive), A2 (`/edge/detections` vs `/events/ingest` — Plano 3/F3), registry estático-vs-declarativo (F5+, não bloqueia RVB), DeepStream (F7).
**Ação do Vitor:** S8 (rotacionar segredo pela app).
