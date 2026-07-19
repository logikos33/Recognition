# Relatório — Trilha de Segurança Edge + Multi-tenancy (2026-07-18)

**Branch:** `claude/edge-security-tenancy-s1` (de `origin/develop`) · **PR:** `risk:security` → **fila humana**
**NÃO promover** para staging/main. Base: develop @ `5f0d8c3c`.
Reconciliação C-04 completa em [`docs/edge/RECONCILIACAO_EDGE_2026-07-18.md`](edge/RECONCILIACAO_EDGE_2026-07-18.md).

Health check: `pytest tests/ -q` → **3665 passed, 6 failed, 56 skipped**. Os 6 failing são
`test_quality_inference_onnx` — **pré-existentes na develop limpa** (provado por baseline com stash;
passam isolados, falham só no full-run por pollution de `sys.modules`), fora do escopo desta trilha.
`ruff check` verde. Sem migrations. Sem mudança no frontend (tsc N/A).

---

## 🔴 BLOQUEANTE DE GO-LIVE (ação do Vitor) — S8

Senha `admin@rvb.com.br` commitada no git durante o embarque do soak. **Não foi tocada por shell/SQL**
(regra). Ação necessária, **pela aplicação**:
1. Rotacionar a senha do usuário `admin@rvb.com.br` pela app (nunca por SQL, nunca commitar a nova).
2. Avaliar expurgo do histórico do git (`git filter-repo`) — custo alto (reescreve hashes, quebra
   clones); decidir se o valor exposto justifica. Recomendação: rotacionar já; expurgo é opcional se a
   senha rotacionada torna o valor antigo inútil.

---

## Achado a achado

| # | Veredito | Evidência / ação |
|---|---|---|
| **S1** escopos nunca aplicados | ✅ **CORRIGIDO** | Decorator `require_device_scope` (`app/core/device_auth.py`) + `authenticate_device` devolvendo scopes. Aplicado a `/heartbeat`, `/config/poll`, `/events/ingest`, `/commands/pending`, `PATCH /commands/<id>`. Novos escopos `commands:read/write`. Testes: 403 sem escopo / 200 com, por rota (`test_edge_config_poll`, `test_edge_commands_scope`, `test_edge_events_scope`). |
| **S2** serve_hls sem tenant | ✅ **CORRIGIDO (flag OFF)** | Decisão do Vitor: **token de playback assinado na URL**. `app/core/playback_token.py` (HMAC+exp, camera-bound). Rota tokenizada `/stream/s/<token>/<file>` (token no PATH → segmentos `.ts` herdam). Enforcement por `HLS_REQUIRE_PLAYBACK_TOKEN` (**default OFF** → zero impacto no player atual). Testes em `test_playback_token`. **Rollout:** o revisor liga a flag após o frontend consumir a URL tokenizada de `/stream/start`. |
| **S3** toggle_module_class cross-tenant | ♻️ **JÁ RESOLVIDO (obsoleto)** | `modules/routes.py:81-105` + `module_service.py:238` já isolam por tenant → 404. Não tocado. |
| **S4** /streams/status público | ✅ **CORRIGIDO** | `streams/routes.py` agora exige role admin/superadmin (auth fora do try amplo). Sem consumidor no frontend. ⚠️ **Reversão** de decisão anterior ("público permanece") — revisor confirma. Testes: `test_streams_status_auth` + `test_streams_routes` atualizado. |
| **S5** rotas sem gate de admin | ✅ **CORRIGIDO** | `GET /edge/commands` e `PATCH /site-gateways/<id>/status` agora exigem admin (`_ADMIN_ROLES` / `gateways:manage`). Testes: `test_edge_admin_gates`. |
| **B4** (contrato) gateway status exige JWT de usuário mas docstring diz "edge" | 📝 **REGISTRADO** | Comentado em `site_gateways/routes.py`; redesenho do caminho do edge = trilha de integração (device auth). Não resolvido aqui (por design). |
| **S6** dois enrollments | 🟰 **MANTIDOS (decisão do Vitor)** | Vitor decidiu **manter os dois** (`devices/claim` HS256 público + `edge/enroll` opaco SHA-256). Documentado abaixo. Nada removido. |
| **S7** drift ADR-0019 | ✅ **CORRIGIDO (doc)** | ADR-0019 ganhou seção "Reconciliação com a implementação real" — device auto-assina, `/enroll` (não `/enrollment/redeem`), `/auth/rotate` inexistente, escopos aplicados. |
| **S8** segredo commitado | 🔴 **AÇÃO DO VITOR** | Ver topo. Não tocado. |

---

## S6 — os dois fluxos de enrollment (mantidos)

| | `devices/` (claim-code) | `edge/enroll` (token opaco) |
|---|---|---|
| Rota pública | `POST /devices/claim` (rate-limit 10/min) | `POST /edge/enroll` |
| Credencial | claim-code 8 chars → JWT HS256 `device_enrollment` | token opaco → SHA-256 vs `enrollment_tokens.token_hash` |
| Ligado à device auth RS256 em produção | não | **sim** (heartbeat, config/poll usam o device auto-assinado) |
| Consumidor no frontend | nenhum | nenhum |

**Decisão:** manter ambos. **Recomendação registrada:** `/devices/claim` é público e órfão — vale
vigiar como superfície de ataque; se um dia não houver plano de uso (UX de claim-code), aposentar.
Não removido nesta trilha por decisão explícita.

---

## Achado novo (fora do PLANO_SEGURANCA — só registrado)

`API_CONTRACT_MAP.md` item #7: `GET /api/alerts/<alert_id>/snapshot` — query sem filtro `tenant_id`,
possível vazamento cross-tenant (P0). Não estava no plano; **não corrigido aqui** (escopo). Recomendo
task própria na trilha de segurança.

Também: `API_CONTRACT_MAP.md` item #8 está **stale** (diz que `edge_events` passa o objeto `request` —
já corrigido). Correção do map = trilha de integração (B3).

---

## O que NÃO foi tocado e por quê

- **S8** (segredo): credencial = ação do Vitor pela app; regra proíbe shell/SQL.
- **B4 / alerts snapshot / contract map**: fora do escopo desta trilha (integração ou task própria).
- **6 testes quality_inference_onnx**: falha pré-existente na develop (pollution de full-run), não
  introduzida aqui — provado por baseline.
