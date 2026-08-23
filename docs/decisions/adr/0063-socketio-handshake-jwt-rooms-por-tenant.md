# ADR-0063 — SocketIO: handshake com JWT e rooms por tenant (namespaces registrados, fim do broadcast)

**Status:** Proposta (2026-08-23) · **Autor:** Vitor Emanuel (Logikos) · **Relaciona:** ADR-0002
(detecções via Redis pub/sub → bridge → browser), ADR-0004 (schema-per-tenant), ADR-0017 (sem
fallback silencioso de tenant), constitution C-01.

## Contexto

O mapa de migração do frontend (PR #523, `docs/migration/inventory/domains/socketio-env.md`,
achados A1/A2) provou, com as versões pinadas em produção (`python-socketio 5.16.3` /
`flask-socketio 5.6.1`), que:

1. **O servidor recusava os namespaces `/monitor`, `/training`, `/quality` e `/admin`.** python-socketio
   ≥ 5 só aceita conexão a um namespace com handler registrado (ou listado em `namespaces=`);
   `create_app()` não registrava handler nenhum. `socketio.test_client(app, namespace='/monitor')
   .is_connected('/monitor')` era `False`. Todo o "tempo real" do front rodava no vazio; as telas
   funcionavam por polling sem saber.
2. **O bridge Redis→SocketIO emitia em broadcast no namespace**, sem room por tenant. No dia em que as
   conexões passassem a aceitar, um tenant receberia detecções/telemetria/inspeções do outro —
   violação direta de C-01.

Além disso, os hooks do front já enviavam o JWT no handshake (`query: { token }`) — que o servidor
nunca leu.

## Decisão

1. **Handler `connect` registrado em `/monitor`, `/training` e `/quality`** (`app/core/socket_auth.py`,
   chamado em `create_app()` logo após `socketio.init_app`, inclusive em TESTING).
2. **JWT obrigatório no handshake.** Fontes, nesta ordem: `auth: {token}` do socket.io-client
   (recomendado — não vai para a URL) e `?token=` na query (compatibilidade; desencorajado, vaza
   para logs de acesso). Mesmo token Bearer da REST. Validação = assinatura + expiração +
   **blocklist** (logout/sessão revogada), igual a `@jwt_required` — `decode_token` sozinho não
   consulta a blocklist.
3. **Sem token, inválido/expirado/revogado, ou sem claim `tenant_schema` → conexão recusada**
   (`ConnectionRefusedError` com motivo curto: `auth_required` / `invalid_token` /
   `tenant_required`). ADR-0017: nenhum fallback de tenant. Superadmin **sem** contexto assumido
   (token sem `tenant_schema`) é recusado — comportamento seguro por padrão; uma room "plataforma"
   é decisão de produto futura.
4. **Conexão aceita entra na room `tenant:<tenant_schema>`** do namespace.
5. **O bridge só emite `to=tenant:<schema>`** (`app/core/socket_bridge.py::route_message`). O tenant
   vem do canal (`quality:*:{schema}:*`, `edge_telemetry:{tenant_id}`) ou de lookup cacheado
   (`det:{camera_id}`, `operations:*:{op_id}`, `training:{job_id}` — `TenantSchemaLookupRepository`,
   só `public.*`). **Não resolveu → descarta e loga**; nunca cai em broadcast. O canal
   `quality:training_progress` passa a carregar o schema (`quality:training_progress:{schema}:{job}`),
   na convenção dos demais canais de quality; a forma antiga é descartada.
6. **`/admin` NÃO é registrado.** Ninguém emite nele (o hook `useAdminWebSocket` está morto e usa URL
   relativa); continua recusado de propósito até existir emissor.
7. **Front:** os 4 hooks vivos passam de `query: { token }` para `auth: { token }`; os 2 hooks de
   qualidade (que não mandavam nada) ganham `auth` com o token da sessão. Shapes dos eventos
   **não mudam** nesta decisão (divergências A5 do mapa são rodada própria).

## Consequências

- Tempo real volta a ser um contrato real (PR #523 o tratava como "inoperante; polling é o
  contrato"). O novo front pode assinar `/monitor`, `/training`, `/quality` com JWT.
- Isolamento por tenant é garantido no servidor (rooms), não no cliente. Testes:
  `tests/unit/core/test_socket_auth.py` (recusa/aceite/isolamento A×B/rooms por namespace) e
  `tests/unit/core/test_socket_bridge.py` (todo emit tem `to=`; sem tenant → drop).
- Custo: um lookup cacheado (1 h hit / 60 s miss) por câmera/operação/job no thread do bridge.
- Dívida explícita: `alert` em `/monitor` e `quality_gate_result` continuam sem emissor (front
  escuta no vazio); eventos com shape divergente (A5) e a decisão sobre room de superadmin ficam
  para ADRs/PRs próprios.

## Alternativas rejeitadas

- **`namespaces='*'` / registrar namespaces sem auth:** faz as conexões aceitarem, mas mantém o
  broadcast cross-tenant (C-01) — pior que recusar.
- **Filtrar no cliente pelo `camera_id`/tenant do token:** o payload já teria saído do servidor para
  o tenant errado; não é isolamento.
- **Room por `tenant_id` em vez de `tenant_schema`:** equivalente; `tenant_schema` foi escolhido por
  ser o que os canais de quality já carregam e o que `get_tenant_schema()` usa na REST.
