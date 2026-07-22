# ADR-0055 — Plano de controle Edge: cinco canais, config versionada por polling

> **Nota de numeração (2026-07-22):** renumerado de 0054→0055 na reconciliação de docs — o número
> 0054 já estava ocupado na develop por `0054-motor-operacoes-e-decisoes-ponte-edge.md` (tópico distinto).

**Status:** Proposta · **Data:** 2026-07-18 · **Autores:** Vitor Emanuel (Logikos)
**Relaciona:** ADR-0019 (device tokens RS256), ADR-0004 (multi-tenant), ADR-0046 (deployment modes),
ADR-0053 (cenário multi-módulo RVB), task-045 (modelo por câmera), task-024 (operation-types)
**Detalhamento:** `docs/edge/PLANO_CONTROLE_EDGE_2026-07-18.md`

## Contexto

A premissa do produto é **controlar o Edge e a operação pelo front, sem tocar no código**. A varredura do repo
real em 2026-07-18 (C-04) mostrou que a premissa é hoje **falsa em quase toda a superfície**, por três motivos:

1. **A ponte não existe.** `GET /api/v1/edge/config/poll` é chamado pelo `edge-sync-agent`
   (`config_poller.py:48`) e **não está implementado** na API — `grep "config"` em `edge/routes.py` retorna zero
   linhas. O `API_CONTRACT_MAP.md:218` documenta a rota como existente, ou seja, a doc diverge do código.
2. **Dois canais estão quebrados desde sempre.** `edge_commands` e `edge_events` passam o objeto `request` do
   Flask onde a função de auth espera a **string do token** → `DecodeError` garantido. Nunca autenticaram.
3. **Parte da config é decorativa.** `cameras.fps_target` e `quality_preset` têm banco, API e UI, mas **nenhum
   consumidor de runtime**; o comportamento real vem de env vars globais (`YOLO_INFERENCE_EVERY_N_FRAMES`,
   `DETECTION_CONFIDENCE_THRESHOLD`). O operador muda na UI e nada acontece.

Adicionalmente: `deepstream/` está **vazio** (só `.gitkeep`) — não existe config de nvinfer nem gerador, então a
decisão "config vem do banco ou de arquivo" está **em aberto**, não é retrabalho.

## Decisão

1. **A integração é modelada como CINCO canais**, não uma API: (1) config cloud→edge por **pull**,
   (2) comandos cloud→edge por **pull**, (3) eventos/detecções edge→cloud por **push**, (4) modelo cloud→edge
   por **pull**, (5) observabilidade edge→cloud por **push**. Cada um com contrato, cadência e modo de falha
   próprios.

2. **Config por polling versionado, escopo = site.** `GET /api/v1/edge/config/poll` com device auth RS256,
   resposta com `config_version` monotônico + `ETag`, e **304 em `If-None-Match`** quando nada mudou.
   Cadência 30–60s (hoje o cliente tem 300s hardcoded).

3. **Reusar o composer de cenário existente.** `scenarios/routes.py` já monta câmera + módulos + classes +
   operações + regras + agenda — é exatamente o payload que o device precisa. Trocar a auth de user-JWT para
   device auth e **não escrever um segundo composer**.

4. **Config ruim não derruba o site.** O device guarda a última config boa; falha ao aplicar → mantém a anterior
   e reporta no heartbeat. Aplicação sem restart, no padrão do `model_watcher.py` (pub/sub + reload localizado).

5. **Fechar o laço decorativo é pré-requisito, não melhoria.** `fps_target`, `quality_preset` e
   `confidence_threshold` passam a ser lidos da config entregue ao edge; as env vars globais equivalentes são
   aposentadas. Enquanto isso não acontecer, a UI mente para o operador.

6. **Ciclo de vida explícito de comando:** `pending → acked → running → done|failed|expired`, com TTL e
   **idempotência por `command_id`** (retry pode reentregar).

7. **Um contrato por canal.** `/edge/detections` (chamado pelo agent, inexistente na API) e `/events/ingest`
   (existe, sem cliente) são resolvidos escolhendo **um** canônico; o outro é removido. Idem para os **dois
   fluxos de enrollment incompatíveis** (`devices/` vs `edge/enroll`).

8. **Distribuição de modelo ao device** via `GET /api/v1/edge/models/<id>/download` com escopo
   `models:download` (previsto no ADR-0019, nunca implementado), URL assinada do R2, checksum e **rollback
   automático** se o engine novo não carregar.

9. **Critério de aceite por fase:** cada fase entrega uma frase verdadeira do tipo *"o operador muda X na UI e o
   Edge obedece, sem SSH"*. Fase que não enuncia isso não terminou.

10. **Segurança é trilha separada** (`PLANO_SEGURANCA_EDGE_2026-07-18.md`), com prioridade alta e revisão humana
    (`risk:security`). Não se mistura com as fases de integração.

## Decisões deixadas EM ABERTO (exigem o Vitor antes da fase correspondente)

- **Registry de operation-types: estático (Python + deploy) ou declarativo (schema em banco)?** Hoje é estático
  (`operations/canonical/__init__.py`), e faltam `attention_points`, `stage_timer`, `crowd_zone`, `dwell_zone` —
  os dois primeiros **bloqueiam o cenário RVB (ADR-0053)**. Enquanto o registry for estático, "sem tocar no
  código" é falso nessa dimensão.
- **DeepStream: gerar config a partir do banco, ou pipeline lê config em runtime?** Decidir **antes** da F7.

## Consequências

- Fases F0–F8 detalhadas no plano; F0 (consertar device auth) e F1 (criar `config/poll`) destravam o resto.
- `docs/API_CONTRACT_MAP.md` precisa ser corrigido em dois pontos (linha 22 e 218) — hoje afirma coisas falsas
  sobre o código, o que induz a próxima sessão ao erro.
- O motor de operações em produção (`operation_results` hoje só populada por `/test`) vira trabalho explícito (F6).
- Telas de ADM que hoje não existem no front (site CRUD, enrollment, gateway, console de comandos) entram como F8.
- ADR-0019 diverge da implementação em rotas e modelo de confiança → reconciliar (item S7 da trilha de segurança).
