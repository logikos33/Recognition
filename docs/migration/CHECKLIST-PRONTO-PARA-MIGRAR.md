# Checklist "PRONTO PARA MIGRAR" — novo frontend assume 100% do backend

> Critérios **objetivos** de cobertura. A migração só é declarada pronta quando TODOS os itens
> abaixo estiverem marcados, com evidência (link para PR/commit/print/teste) ao lado de cada um.
> Fonte dos números: `docs/migration/inventory/map_summary.json` (regere com
> `python3 tools/build_migration_map.py build`). Zero mudança de comportamento no backend até lá.

## 0. Pré-condições (antes de começar a migrar)

- [ ] Inventário regenerado no HEAD que será o alvo da migração: `cd services/api && FLASK_ENV=testing python ../../tools/api_inventory.py && python ../../tools/frontend_api_calls.py && cd ../.. && python3 tools/build_migration_map.py inputs build` — diff do `docs/migration/inventory/endpoints.json` revisado (endpoint novo/removido desde o mapa = mapa desatualizado).
- [ ] Coluna **NOVO FRONT** do `MAPA-MIGRACAO-FRONTEND.md` preenchida para **100 %** das linhas (`cobre` / `não cobre` / `n.a.`) — nenhuma célula vazia.
- [ ] Para cada `FRONT-ATUAL` marcado `não cobre`: decisão consciente registrada (dono + data + motivo) — "não cobre" sem decisão = bloqueio.
- [ ] Para cada `GAP-DE-PRODUTO`: decisão `cobre` (entra no design) ou `não cobre` (fica sem UI, registrado) — ver `LISTA-PARA-O-DESIGN.md`.
- [ ] `BACKEND-ONLY` e `ÓRFÃO`: `n.a.` por padrão; nenhum removido nesta rodada (remoção de órfão = rodada própria com issue).

## 1. Endpoints REST (cobertura funcional)

- [ ] 100 % dos endpoints `FRONT-ATUAL` com `cobre` têm chamada equivalente no novo front (mesmo método + path + auth + envelope) — verificável rodando `tools/frontend_api_calls.py` apontado para o novo front (`FRONT_SRC`) e comparando o conjunto de regras casadas com o do front atual: **conjunto novo ⊇ conjunto atual − descartes conscientes**.
- [ ] Nenhuma chamada do novo front **sem regra** no matcher (seção "SEM regra" de `consumers.md` vazia) e nenhuma chamada **dinâmica** não resolvida.
- [ ] Os 5 bugs de contrato do front atual NÃO foram copiados (`useScenario` → `/api/v1/cameras/<id>/scenario`; `PATCH gate/config` e `export-wiser*` não existem no back; `PATCH gate/stations/<code>` é `PUT`; `gate/photos/<path>` não existe) — ou o backend ganhou os endpoints em PR próprio antes.
- [ ] Aliases `/api` × `/api/v1` (cameras, counting, health): o novo front usa **uma** família por recurso e isso está escrito no mapa (recomendado: `/api/v1` onde existir).
- [ ] Envelopes não-padrão tratados: CSV/PDF/binário (`downloadBlob`), `jsonify` cru, redirect, 207 multi-status, 202 + polling.
- [ ] Paginação/cursor, filtros e ordenação replicados exatamente como o back espera (cursor posicional da fila de reapresentação, `page/per_page`, `limit/offset`).
- [ ] Uploads multipart com os mesmos nomes de campo e limites (vídeos de treino, frames, logo de branding, snapshots).
- [ ] Tratamento de 401 (expiração + restauração de impersonation/contexto), 403, 404 cross-tenant (C-01), 409 (seat limit), 429 (rate limit) igual ou melhor que o atual.

## 2. Tempo real (SocketIO)

- [ ] Todos os eventos da tabela "Contrato tempo real" com status `ok` são assinados pelo novo front nos namespaces corretos (`/monitor`, `/training`, `/quality`) com o mesmo shape de payload.
- [ ] Assinaturas mortas e emits sem handler do front atual (`subscribe_camera`/`unsubscribe_camera`, namespace `/admin`) **não** são copiados — ou ganham handler no servidor em PR próprio.
- [ ] `wsUrl` derivado da mesma regra (`VITE_WS_URL` → fallback `VITE_API_URL`), transports/path iguais, reconexão com backoff.
- [ ] Filtro por tenant do broadcast verificado (se o servidor emite sem room por tenant, o novo front filtra pelo `camera_id`/tenant do token e o achado está registrado).

## 3. Ambiente e contrato transversal

- [ ] `VITE_API_URL` / `VITE_WS_URL` configurados nos 3 ambientes (Desenvolvimento / staging=produção / main) e `API_BASE = VITE_API_URL + /api`.
- [ ] `Authorization: Bearer` em toda chamada autenticada; chaves de `localStorage` (`token`, `user`, `impersonation*`, `tenant_context*`) ou equivalente novo com a mesma semântica de restauração.
- [ ] Impersonation "ver como" e contexto de tenant assumido: início/fim/expiração e banner.
- [ ] URLs pré-assinadas (R2) consumidas direto pelo browser; CORS do bucket confirmado para a origem do novo front.
- [ ] Token de playback HLS (`/api/cameras/<id>/stream/s/<token>/…`) obtido e renovado como hoje (m3u8 sem token = 404).
- [ ] Branding público (`GET /api/v1/tenant/branding`, sem auth) carregado no boot; white-label por tenant.
- [ ] Timeouts (15 s REST / 30 s download) e toasts de erro equivalentes.
- [ ] CORS da API (`CORS_ORIGINS`) inclui a origem do novo front em cada ambiente.

## 4. Comportamentos (contrato além do REST)

- [ ] Fluxos multi-etapa documentados nas seções "Fluxos" do mapa reproduzidos na mesma ordem: login→`/auth/me`, câmera→probe→config→live view, upload→processa→poll→resultado (treino/propagação/busca), propose→confirm (anotação/propagação), enroll→heartbeat (só visualização no front), harness/test console (superadmin).
- [ ] Gating por role/permission/módulo/feature flag aplicado nas mesmas telas (superadmin-only → 404, não 403).
- [ ] Polling e intervalos (progresso de job, fila, live status) iguais ou melhores, sem aumentar carga na API.

## 5. Prova

- [ ] Suíte e2e do front novo cobre pelo menos os fluxos críticos do RVB (login, live view, galeria/anotação, alertas/eventos, admin de câmeras) no DEV.
- [ ] Smoke contra DEV com o novo front servido por URL própria; `tools/frontend_api_calls.py` sobre o novo front commitado junto (inventário de consumo do novo front no repo).
- [ ] Decisão registrada (ADR) do corte: data, quem aprovou, o que foi conscientemente descartado.
