# ADR-0054 — Motor de Operações em produção + decisões da ponte plataforma↔edge (D1–D4)

**Data:** 2026-07-21
**Status:** Proposta
**Contexto:** Go-live RVB — Bloco 2 (ponte) e Bloco 3 (cenário). Decisões D1–D4 dadas pelo Vitor em 2026-07-21.
**Relacionado:** ADR-0002 (Redis pub/sub de detecção), ADR-0019 (device auth), ADR-0053 (cenário multi-módulo RVB).

---

## Contexto

Até 2026-07-21, `BaseOperation.evaluate()` só rodava na rota `/operations/<id>/test` e `operation_results` não era
populada por worker nenhum — a operação configurada não produzia resultado em produção. As classes canônicas
(`epi_zone`, `counting_line`, `attention_points`, `stage_timer`, …) e o schema (`operations`, `operation_results`
com `version`/`last_value_json`) já existiam; faltava o **motor** que avalia contra o stream de detecção.

Quatro decisões de arquitetura destravavam essa peça (respostas do Vitor):

## Decisões

### D1 — Registry de operation-types: **DECLARATIVO**
O mecanismo de tipos de operação será **declarativo** (registro em runtime + schema em banco), não estático
(classe + deploy). Cumpre a tese do produto: configurar sem tocar no código; tipos novos podem nascer sem deploy.
`attention_points` e `stage_timer` (hoje classes) migram para o modelo declarativo. Inspiração de padrão: plugin
auto-descritivo (declara parâmetros + tipos + doc → UI se gera).
> **Escopo:** o mecanismo declarativo é trabalho próprio (PR futuro). Este ADR e o PR do **motor** usam o
> `OperationTypeRegistry` atual como fonte de tipos; o motor foi desenhado para ser **agnóstico à origem do tipo**
> (consulta o registry), então trocar o backend do registry para declarativo não muda o motor.

### D2 — DeepStream config: **RUNTIME + RELOAD ESTRUTURAL**
O pipeline lê a config da ponte que já existe (F1, `GET /api/v1/edge/config/poll`); **não** gerar-e-reiniciar.
- **Parâmetros quentes** (FPS/interval, threshold, ROI, zona, regra) aplicam **sem restart**.
- Só mudança **estrutural** (troca de modelo, add/remove de câmera, mudança de batch) dispara **reload controlado**,
  no mesmo padrão do `model_watcher.py`. O conjunto "estrutural" deve ser definido/documentado explicitamente.
- **No motor de operações (cloud):** a mudança de config de uma operação é tratada como reload da instância —
  `operations:reload:{op_id}` reconstrói a instância; o estado vivo (cronômetro/contador) é **resetado** (config
  nova = comportamento novo).

### D3 — Canal de detecção edge→cloud: **`/api/v1/edge/events/ingest` é o canônico**
`events/ingest` (existe, testado, com dedup) é o canal oficial. **`/detections` não existe e não será
implementado** — o uploader do edge-sync-agent aponta para `events/ingest`; remover referências a `/detections`.
(O stream ao vivo `det:{camera_id}` no Redis pub/sub — ADR-0002 — segue sendo a via de baixa latência que o
`socket_bridge` e agora o motor de operações consomem.)

### D4 — Enrollment duplo e `/auth/rotate`: **BACKLOG**
Não entra antes do go-live. RVB = um device, um site; `edge/enroll` basta. Rotação sem re-enrollment é
conveniência de frota. Pós-go-live: unificar `edge/*` com o `devices/` órfão (limpeza da trilha de segurança,
não-bloqueante) e avaliar `/auth/rotate` quando houver frota.

## Decisão de implementação — OperationsEngine (este PR)

Motor **puro e injetável** (`app/domain/services/operations/engine.py`) dirigido por um runner de I/O
(`app/core/operations_worker.py`) que assina `det:*` (mesmo canal do `socket_bridge`) e `operations:reload:*`:

- `load_all()` monta `camera_id → [operações ativas]` (query cross-tenant **de sistema**, `list_all_active`);
  recarrega a cada 30s como rede de segurança. Preserva estado de ops cuja `version` não mudou.
- `process_frame(camera_id, detections, frame_meta)` avalia cada operação, **carrega estado entre frames**, e
  persiste com **throttle** (na mudança de condição OU a cada `result_interval_s`) — a 5 FPS × dezenas de câmeras,
  gravar todo frame explodiria `operation_results`. `last_value_json` (badge ao vivo) atualiza na mudança OU a cada
  `live_interval_s`, e publica `operations:status:{op_id}` (o `socket_bridge` já encaminha ao frontend).
- Isolamento: uma operação que estoura não derruba o frame — vira `status='error'`.
- Hot-reload (D2): `create/update/delete` de operação publicam `operations:reload:{op_id}`; o worker reconstrói ou
  remove a instância. `update` incrementa `version`.
- **Opt-in** por `OPERATIONS_WORKER_ENABLED=true` (+ `REDIS_URL`); no-op caso contrário. Roda no processo da API
  (junto do `socket_bridge`), podendo migrar para worker dedicado se o volume exigir.

## Consequências
- **Positivo:** operação configurada passa a produzir resultado em produção (fecha o Bloco 3 item 2). Motor
  testável sem Redis/banco (10 testes unitários). Contrato de reload/status já casado com o `socket_bridge`.
- **Positivo:** desenho agnóstico ao registry → a migração D1 (declarativo) não reescreve o motor.
- **Negativo/aberto:** throttling é por intervalo fixo (config global) — pode virar por-operação depois. Rodar no
  processo da API é simples mas acopla; mover para worker dedicado é o próximo passo se o volume subir.
- **Aberto (D1):** o mecanismo declarativo em si é PR futuro; enquanto isso os tipos vêm do registry estático.

## Alternativas consideradas
- **Avaliar no edge (DeepStream) em vez de cloud:** menor latência, mas duplica a lógica de operação no C++/edge e
  perde o reuso das classes Python já testadas. Rejeitada para o go-live; o edge entrega detecção, a cloud avalia
  operação.
- **Celery task por frame:** overhead de broker por frame a 5 FPS × N câmeras é proibitivo. Um subscriber
  long-running (como o `socket_bridge`) é o padrão certo para stream.
