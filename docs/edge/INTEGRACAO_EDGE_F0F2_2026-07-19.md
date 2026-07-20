# Integração Recognition ↔ Edge — F0–F2 (2026-07-19)

**Branch:** `claude/edge-integration-f1f2` (de `origin/develop`) · **PR:** para develop, **não promover**.
Trilha SEPARADA da segurança (PR #199, `risk:security`). Base: develop @ `5f0d8c3c`.
Reconciliação C-04: [`docs/edge/RECONCILIACAO_EDGE_2026-07-18.md`](RECONCILIACAO_EDGE_2026-07-18.md).

## Decisões do Vitor (registradas)
1. **Detecções canônicas = `/api/v1/edge/events/ingest`** — `/edge/detections` NÃO será implementado; o `uploader.py` aponta para `/events/ingest`. (afeta F3)
2. **Registry de operation-types: estático por ora** — RVB já desbloqueado (tipos existem); declarativo vira backlog. (F5)
3. **DeepStream lê config em runtime** (hot-reload, sem restart). (F7)
4. **Enrollment: manter os dois fluxos** (decidido na trilha de segurança).

---

## Programa materializado (F0–F8)
`tools/agent-driver/tasks/task-113..121-edge-*.md` — F3–F8 ficam **PENDENTES** (especificadas, não executadas), com as decisões acima embutidas.

## F0 — Fundação (device auth) — ✅ JÁ RESOLVIDO + doc corrigida
- B1/B2 (device auth passava o objeto `request`; 500 em vez de 401) **já corrigidos na develop (WS10)** — evidência na reconciliação. Marcados OBSOLETOS, não "recorrigidos".
- **Feito aqui:** `API_CONTRACT_MAP.md` — itens #8 / linha 233 / 603 (que ainda afirmavam o bug presente) marcados RESOLVIDO; linha 218 atualizada para o contrato F1.

## F1 — A ponte config/poll — ✅ EXECUTADO (núcleo) + resto escopado
- **Executado:** versionamento por conteúdo. `GET /config/poll` agora devolve `config_version` + header `ETag`; `If-None-Match` → **304** quando nada mudou (**sem migration** — hash do payload). Cliente `config_poller.py` envia `If-None-Match`, trata 304 (mantém última config boa, não reaplica), grava o ETag só após aplicar; intervalo 300s→**45s**.
- **Config ruim não derruba o site:** o cliente só substitui o estado num 200 aplicado com sucesso; 304/erro preservam a última config boa.
- **Escopado (RESTANTE, em task-114):** enriquecer o payload reusando o composer de `scenarios/` (módulos+operações+regras+agenda por câmera) — hoje `/config/poll` só devolve câmeras. Exige extrair `compose_camera_scenario` para um service e revisar C-05. Deixado como próximo passo do F1 para não inflar este PR nem arriscar vazamento de credencial sem revisão.
- **Testes:** servidor (ETag/config_version/304/mudança) + cliente (If-None-Match/304/last-good) — 11 + 3 novos, verdes.

**Frase de aceite (provada por teste):** "config muda → device recebe nova `config_version` no próximo poll; nada muda → 304, sem repassar 28×payload."

## F2 — Fechar o laço decorativo — ⏸️ ESPECIFICADO, não executado (needs Jetson)
- Confirmado real: `fps_target`/`quality_preset`/`confidence_threshold` sem consumidor de runtime; comportamento vem de env globals.
- **Não executado neste PR** porque o critério de aceite é *"muda o FPS na UI → o pipeline no Jetson passa a rodar naquele FPS, provado por telemetria"* — a **prova exige o pipeline rodando no box**, indisponível neste ambiente. Escopado em task-115 com a fonte confirmada (config do F1, por câmera) e a env global rebaixada a fallback. Fazer no Jetson com evidência de telemetria.

---

## ⚠️ Conflito esperado no merge
Este PR e o PR de segurança (#199) **ambos editam `poll_edge_config`** (`edge/routes.py`): segurança
adiciona `@require_device_scope` + `g.device_ctx`; integração adiciona ETag/304. São compatíveis —
quem mergear por segundo resolve unindo os dois (decorator + versionamento). Recomendo mergear #199
primeiro (prioridade) e rebasear este.

## Health check
- `pytest` (api) + `pytest` (edge-sync-agent) verdes na área; ruff verde; **sem migrations**; sem frontend (tsc N/A). As 6 falhas `quality_inference_onnx` do full-run são pré-existentes na develop.

## Decisões em aberto restantes (do Vitor, para fases futuras)
Nenhuma bloqueante para F0–F2. As 4 acima cobrem F3/F5/F7. F4/F6/F8 não têm decisão pendente.
