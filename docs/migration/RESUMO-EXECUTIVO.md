# Resumo executivo — Mapa 100 % do backend para a migração do frontend

> Rodada de **mapeamento** (2026-08-23) sobre `origin/develop` @ `98bff30e` (PR #522). Zero mudança de comportamento no ar; nenhum endpoint removido. Tudo que está aqui nasce de três fontes reproduzíveis commitadas em `tools/`: o `url_map` real do Flask (`api_inventory.py`), o consumo real do front resolvido pelo matcher do Flask (`frontend_api_calls.py`) e o banco DEV real (`db_schema_snapshot.py`). Números: `docs/migration/inventory/map_summary.json` e `summary.json`.

## Entregáveis

| # | Entregável | Onde |
|---|---|---|
| 1 | Mapa-contrato por domínio (tabela completa + coluna **NOVO FRONT** vazia + regra de fechamento) | [`MAPA-MIGRACAO-FRONTEND.md`](./MAPA-MIGRACAO-FRONTEND.md) (gerado) |
| 2 | `API_CONTRACT_MAP.md` apontando para o mapa novo (sem duplicar verdade) | [`../API_CONTRACT_MAP.md`](../API_CONTRACT_MAP.md) |
| 3 | Lista para o design (linguagem de produto) | [`LISTA-PARA-O-DESIGN.md`](./LISTA-PARA-O-DESIGN.md) (gerado) |
| 4 | Este resumo (contagens + riscos) | `RESUMO-EXECUTIVO.md` |
| 5 | Checklist "PRONTO PARA MIGRAR" | [`CHECKLIST-PRONTO-PARA-MIGRAR.md`](./CHECKLIST-PRONTO-PARA-MIGRAR.md) |
| — | Inventário determinístico + saídas verificadas por domínio | `inventory/` (`endpoints.json`, `consumers.json`, `classification.json`, `db_schema_dev.json`, `domains/*.json`, `domains/*.md`) |
| — | Scripts reproduzíveis | `tools/api_inventory.py`, `tools/frontend_api_calls.py`, `tools/db_schema_snapshot.py`, `tools/build_migration_map.py` (`inputs` · `build` · `design` · `check`) |

## Contagens

| Métrica | Valor |
|---|---|
| Endpoints (método × path) no `url_map` | **421** (353 paths únicos · 55 blueprints · 402 operações distintas — 19 aliases `/api`↔`/api/v1`, `/health`↔`/api/v1/health`, catch-all) |
| **FRONT-ATUAL** (o front de hoje consome — evidência arquivo:linha viva) | **207** |
| **BACKEND-ONLY** (edge / worker / callbacks / scripts / infra) | **31** |
| **ÓRFÃO** (ninguém chama — sinalizado, não removido) | **61** |
| **GAP-DE-PRODUTO** (o back suporta, o front não usa — avaliar no design) | **122** |
| Chamadas HTTP do front extraídas | 328 (318 casam com regra; **10 sem regra = bugs do front**; 0 dinâmicas não resolvidas) |
| Código morto no front com chamadas | 6 arquivos não alcançáveis de `main.tsx` + 45 wrappers de service sem chamador (não contam como consumo) |
| Eventos SocketIO | servidor emite **13 eventos** em 3 namespaces (`/monitor`, `/training`, `/quality`) via bridge Redis; front assina 16 nomes em 7 hooks — **6 nunca chegam** (`alert`, `quality_gate_result`, 4 do `/admin`), **2 emits sem handler** (`subscribe_camera`/`unsubscribe_camera`); `training_progress` sem publicador |
| Env/contrato do front | `VITE_API_URL`, `VITE_WS_URL` (+ `FRONTEND_URL` do lado da API para o link de reset de senha); header só `Authorization: Bearer`; 9+ chaves de `localStorage`/`sessionStorage` |
| Banco DEV | 138 tabelas em 4 schemas (`public` 82 · `rvb`/`dev`/`admin` 18–19 cada, **todas vazias**); 16/82 tabelas `public` e 2/18 de tenant não citadas por nenhum domínio |
| Achados registrados nos domínios | **185** (43 P1 · 0 P0 · restante P2/P3) — lista completa em `MAPA-MIGRACAO-FRONTEND.md` (seção "Achados" de cada domínio) |
| Itens para o design | **114** (em linguagem de produto) + anexo com os 122 GAPs |

Por domínio (FRONT-ATUAL / BACKEND-ONLY / ÓRFÃO / GAP): auth-identity 17/0/0/3 · admin-core-a 22/0/4/4 · admin-core-b 17/1/0/13 · admin-aux 24/5/4/6 · cameras-streams 19/1/15/18 · training 28/3/9/5 · models-datasets-rules 8/0/2/16 · quality 29/0/2/19 · edge-fleet 17/13/2/13 · events-alerts-media 10/1/7/18 · ops-dashboard-misc 16/7/16/7.

## Os 5 maiores riscos da migração (na minha leitura)

1. **[corrigido em PR #524 / ADR-0063 — pendente de merge/promoção] O tempo real não funcionava no servidor em `98bff30e` — e quando funcionasse, vazaria entre tenants.** Com as versões pinadas em produção (`python-socketio 5.16.3` / `flask-socketio 5.6.1`), `create_app()` não registra handler nem `namespaces=`; **reproduzi localmente**: `/` conecta, `/monitor`, `/training`, `/quality`, `/admin` são recusados (`server.namespaces=['/']`). Todas as telas funcionam por polling sem saber. Além disso o bridge emite em broadcast sem `join_room(tenant)` (C-01). **Consequência:** o novo front não pode ser desenhado "WebSocket-first" até o backend (a) registrar `connect` por namespace com JWT e rooms por tenant, (b) alinhar os shapes (5 divergências listadas em `socketio-env.md` A5). Polling continua sendo o contrato real.
2. **O front atual já chama coisas que não existem — o novo não pode copiar.** 10 chamadas sem regra (4 endpoints de qualidade inexistentes — `gate/photos`, `export-wiser`×2, `gate/config`; método errado `PATCH gate/stations`; cenário sem `/v1` ×2; CSV com **JWT na query string**), drift de shape (`res.status==='success'` vs `success:true` no wizard de câmeras, `data.inspection` vs flat), envelopes não padronizados (erros do Flask-JWT `{status,data}` + 422 para token inválido, `/health*`, CSV, SSE) e o **catch-all do SPA devolvendo 200 `{"status":"API online"}` para qualquer GET desconhecido** — um front novo baseado nos tipos TS atuais herdaria tudo isso. Mitigação: contrato = `MAPA` + e2e contra a API DEV, nunca os `types/*.ts` de hoje.
3. **Isolamento multi-tenant tem furos que a migração pode perpetuar ou expor.** `risk:security` (→ fila de revisão humana, ver bloco abaixo): cross-tenant 200 em `POST /api/alerts/<id>/acknowledge`, `GET /api/cameras` para role `admin`, `GET /api/cameras/<id>/alerts`, `GET /api/training/jobs/<id>/status`, `POST /api/v1/edge/commands`, `PUT /api/v1/site-gateways/<id>`, `POST /api/v1/videos/<id>/finalize-extraction`; bypass de aprovação em `POST /api/training/models/<id>/activate`; `PATCH /api/modules/<code>/classes/<id>` grava no catálogo **global**; `edge_telemetry` em broadcast. O novo front deve usar **só** as rotas canônicas indicadas no mapa (ex.: `/api/v1/models/<id>/activate`, alertas pelo domínio `alerts`) e o backend precisa fechar esses furos com teste falha-antes/passa-depois.
4. **Duas famílias de rota e escopos legados coexistem com comportamentos diferentes.** 19 aliases `/api`↔`/api/v1` (ok), mas também duplicatas **não** equivalentes: branding (2 APIs, formatos incompatíveis, uma `DEPRECATED` que sobrescreve o JSONB), retenção (`/api/cameras/tenant/retention` lê coluna inexistente → 500; `/api/v1/tenant/retention` funciona), treino legado escopado por `user_id` em vez de tenant (`/api/training/jobs|models|videos`), demo-videos fora de `/api/v1/admin`. Mitigação: o mapa marca a família canônica em `behavior_notes`/findings; a migração escolhe uma por recurso e o backend abre uma rodada de depreciação explícita (não nesta).
5. **Sessão e identidade não têm "fonte de verdade no servidor".** JWT de 24 h em `localStorage`, sem refresh; `GET /api/auth/me` **não devolve `tenant_schema`/`modules`** e ninguém o chama — o shell inteiro (sidebar, módulos, `can()`) é hidratado do `localStorage`; impersonation e contexto assumido dependem de backup/restauração local e o `renew` devolve `user` sem `email/name`. O novo front precisa de um boot que valide sessão no servidor — o que exige `/me` completo (ou `/me` + `/permissions/mine`) — **antes** de desenhar o shell. Soma-se: auto-cadastro quebrado ponta a ponta (cria conta órfã sem tenant).

Riscos "de escopo" que não entram no top-5 mas pesam: **122 GAPs** (quase 1/3 da API não tem UI — admin de tickets/usuários/workers, datasets/registry de modelos, regras de alerta, gravadores, quality gate completo, relatórios); **edge→cloud**: o `edge-sync-agent` postava detecções em `POST /api/v1/edge/detections`, rota inexistente (ingest real é `/edge/events/ingest`) — corrigido em [#529](https://github.com/logikos33/Recognition/pull/529)/ADR-0064 (uploader alinhado + relay opt-in; produtor no box ainda pendente) — BACKEND-ONLY, mas é a fonte dos dados "ao vivo" que o front mostra; **Swagger** cobre só ~35/421 rotas (não serve de contrato); **datas** em formato misto (RFC 822 via `jsonify` default × ISO) e 32 colunas `timestamp without time zone`; **paginação** heterogênea (page/per_page · limit · limit+offset · cursor).

## `risk:security` — fila de revisão humana → PRs abertos em 2026-08-23

Conforme CLAUDE.md, `risk:security` parou a fila; cada item foi confirmado no código, ganhou teste falha-antes/passa-depois e um PR por grupo coeso (cross-tenant → 404; override de superadmin preservado e testado): **[#525](https://github.com/logikos33/Recognition/pull/525)** alerts/cameras/videos · **[#526](https://github.com/logikos33/Recognition/pull/526)** edge · **[#527](https://github.com/logikos33/Recognition/pull/527)** treino/módulos · **[#528](https://github.com/logikos33/Recognition/pull/528)** admin · (SocketIO: **[#524](https://github.com/logikos33/Recognition/pull/524)**). Arquivo:linha no JSON do domínio (`inventory/domains/*.json`, `findings` marcados `[CORRIGIDO em PR #…]`):

- `POST /api/alerts/<alert_id>/acknowledge` — UPDATE sem `tenant_id` (IDOR cross-tenant) — `events-alerts-media` → #525
- `GET /api/cameras` com role `admin` — `CameraRepository.get_all()` sem filtro de tenant (+ get/update/delete/start/test/config) — `cameras-streams` → #525
- `GET /api/cameras/<camera_id>/alerts` (→ #525) e `GET /api/training/jobs/<job_id>/status|progress` (→ #527) — cross-tenant 200 — `training`
- `POST /api/v1/edge/commands` (site_id não validado contra o tenant) e `PUT/GET /api/v1/site-gateways/<site_id>` (upsert sem tenant; GET sem gate) — `edge-fleet` → #526
- `POST /api/v1/videos/<video_id>/finalize-extraction` — sem checagem de posse/tenant — `events-alerts-media` → #525
- `POST /api/training/models/<model_id>/activate` — ativa qualquer modelo sem posse nem `require_training_role('approve')` (bypass de `/api/v1/models/<id>/activate`) — `training` → #527 (delega ao canônico)
- `PATCH /api/modules/<code>/classes/<class_id>` — escreve no catálogo global `public.module_classes` — `models-datasets-rules` → #527 (só superadmin)
- `POST /api/v1/admin/test-console/seed` atrás de `require_admin` com senha default hardcoded — `admin-aux` → #528
- SocketIO `edge_telemetry`/`detection`/`quality_*` em broadcast sem room por tenant — `socketio-env.md` A2 → #524
- `DELETE /api/admin/roles/<id>` conta usuários sem filtro de tenant (409 vaza existência) — `auth-identity` → #528
- CSV de peças com JWT em query string (`QualityReportsPage.tsx:136-150`) — front (pendente; é do front atual — o novo front não copia)

## Método (para quem for auditar)

1. `tools/api_inventory.py` importa `create_app('testing')` e despeja o `url_map` (421 regras) com arquivo:linha, decorators e marcadores estáticos (AST) — determinístico (2 execuções idênticas). Rotas só-produção (`/api/v1/docs`, `/api/v1/apispec.json`) listadas à parte em `summary.json`.
2. `tools/frontend_api_calls.py` extrai `api.*`, `fetch`, `xhr.open`, templates `${API_BASE}` e resolve com `app.url_map.bind().match` (mesma resolução de produção); alcançabilidade por arquivo (BFS de `main.tsx`) **e por função** (wrapper exportado sem referência viva = morto); também consumidores edge/worker/scripts.
3. `tools/db_schema_snapshot.py` — schema + `count(*)` do DEV, somente leitura.
4. 11 leituras linha a linha por domínio → JSON; 11 verificadores adversariais (rótulos, auth, evidência, tabelas, findings); 3 transversais (SocketIO/env, fluxos pages, fluxos modules); 1 crítico de completude (cobertura 421/421 confirmada). `tools/build_migration_map.py check` = 0 inconsistências entre rótulo e evidência do scanner.
5. O mapa e a lista para o design são **gerados** (`build`/`design`); correções vão no JSON do domínio, nunca no Markdown.

## Próximos passos sugeridos (fora desta rodada)

1. Design cruza a coluna **NOVO FRONT** (207 FRONT-ATUAL + 122 GAP) usando `LISTA-PARA-O-DESIGN.md`.
2. Backend abre 3 frentes **antes** de qualquer corte: (a) SocketIO — handlers de namespace + JWT + rooms por tenant (**PR #524 / ADR-0063 aberto**); (b) fila `risk:security` acima (**PRs #525–#528 abertos**; uploader do edge em **#529**); (c) depreciação explícita das duplicatas (`/api` legado, branding, retention, treino por `user_id`).
3. Regenerar o inventário a cada PR que toque `services/api/app/api` ou `apps/frontend/src` (`inputs` → `check` → `build`), para o mapa não envelhecer como o `API_CONTRACT_MAP.md` de julho.
