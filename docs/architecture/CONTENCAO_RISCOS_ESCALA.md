# Contenção de riscos em escala (30+ câmeras) — registry

> **Data:** 2026-06-05 · **Base:** `docs/research/PESQUISA_CV_30_CAMERAS.md` (pesquisa em fóruns).
> **Regra:** cada risco real da pesquisa tem uma **contenção implementada com o que já temos** (config de
> cenário, validators, heartbeat, alert_rules, frames, model-rollout, edge-agent) e uma **task** que a entrega.
> Gates: 🟢 AUTO (fila) · 🟠 MIGRATION (checkpoint) · 🔴 HARDWARE (Mini PC).

## Matriz risco → contenção → capacidade existente → task

| # | Risco (pesquisa) | Contenção (com o que já temos) | Capacidade que reusa | Task | Gate |
|---|---|---|---|---|---|
| R1 | Decode satura ~20 streams/GPU; 28 câmeras passa disso | Detectar na **sub-stream** (não na main) + **H.265** + GPU dimensionada por decode | config por câmera (`operations`), DeepStream spec | **041** (campo `detection_stream`/`codec`) + **032** | 🟠 + 🔴 |
| R2 | Câmera trava conta após ~6 logins falhos (pior com múltiplas sessões) | **1 conexão RTSP por câmera** + **circuit-breaker de auth** (para após N falhas) + valida URL antes | `RTSPUrlValidator` (✓), `camera_manager` | **034** + **041** (`max_auth_failures`) | 🔴 + 🟠 |
| R3 | RTSP instável ("no frames in 20s"), reconnect storm | Reconnect com **backoff + jitter** + watchdog por câmera + `drop-on-latency` | backoff já no edge-agent (**028** ✓), reconnect do `camera_manager` | **034** + **035** | 🔴 |
| R4 | Banda satura (switch entrega ~50% do nominal) | Sub-stream pra detecção + **processar no edge, mandar só metadados** + telemetria de banda no heartbeat | arquitetura edge, heartbeat (O1 ✓) | **032** + **035** | 🔴 |
| R5 | Falsos-positivos em escala (IR/insetos, sombra, folhagem) | **confidence** + **máscaras (exclude zones)** + **perfil dia/noite** por câmera | `operations.config` (`confidence_threshold` ✓, `zone_points` ✓) | **039** | 🟢 |
| R6 | Contagem degrada (92% detecção → 85% contagem); 1 frame é fraco | **Voto majoritário multi-amostra** na linha + debounce de direção | `counting_line` op-type (**024** ✓) | **038** | 🟢 |
| R7 | Falha silenciosa (câmera para sem alerta) + config drift | **Alerta de liveness POR CÂMERA** (não só site offline) + auditoria de drift | heartbeat + `alert_rules` + painel Sites&Saúde (O1 ✓) | **040** | 🟢 |
| R8 | Batch DeepStream instável (batch-80 crasha; 32 estável) | **batch≤32 + interval + `drop-on-latency=1`** + **profilar NVDEC primeiro** | DeepStream spec | **032** + **035** | 🔴 |
| R9 | "Ninguém compra detecção crua" — precisa fim-a-fim | **Evidência (timestamp+local+frame) + alerta instantâneo** | `alert_rules` + `frames` (✓) | já existe; reforço no **037** | 🔴 |
| R10 | Modelo PPE genérico; precisa fine-tune + retreino contínuo | Fine-tune por planta + **retreino disparado por drift** + **canário** | model-rollout (**025** ✓, canário/pin) + training | trilha de modelos (humano+dados) + eval por módulo | — |

## Contenções já entregues (não precisam de task nova)

- **R3/R4 offline:** o edge-agent core (**028**, mergeado) já tem buffer SQLite durável (WAL, FIFO, sem perda — `mark_sent` só após 200) + uploader idempotente (`X-Batch-Id` SHA-256) + **backoff limitado 30→300s**. Isso já contém "cloud caiu / blip de rede": eventos drenam ao voltar, sem duplicar.
- **R9 evidência:** `alert_rules` + `frames` já capturam o evento com frame. Contenção = garantir no go-live (037) que o alerta sai **instantâneo** e carrega a evidência (timestamp + câmera/site + snapshot).
- **R10 rollout:** `model-rollout` (**025**) já dá pin de versão + canário por tenant×módulo — base pra subir modelo novo sem risco. Falta só o **gatilho de retreino por drift** (trilha humana+dados, eval por módulo — ver `PLATAFORMA_CENARIOS.md §4`).

## Detalhe das contenções de edge (a embutir em 032/034/035 quando o PC chegar)

- **032 (DeepStream):** inferir na **sub-stream**; `batch-size≤32` + `interval` (frame-skip) + `drop-on-latency=1`; **medir utilização do NVDEC antes de tunar** qualquer outra coisa; preferir **H.265** nas câmeras.
- **034 (edge-agent real):** **uma** conexão RTSP por câmera (nunca múltiplas sessões na mesma); reconnect **exponencial com jitter**; **circuit-breaker de auth** — após N falhas de login, parar de tentar e emitir evento de saúde (evita lockout da câmera).
- **035 (self-healing):** **circuit-breaker de GPU/decoder** — quando o NVDEC satura, derrubar FPS antes de travar; **watchdog por câmera** (last-frame); telemetria de **banda + profundidade de fila** no heartbeat.

> Estas três entram como seção "Contenção de risco (pesquisa 2026)" nos specs 032/034/035 (hardware), pra não se
> perderem até o Mini PC chegar. Fonte de verdade: este registry.
