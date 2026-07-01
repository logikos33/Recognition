# Roadmap Go-Live RVB — Índice completo de tasks (início → fim)

> **Data:** 2026-06-04 · **Objetivo:** mapa de TODA a entrega restante até o sistema rodar (3 frentes RVB +
> multi-módulo + edge). Cada task tem um **gate**:
> - 🟢 **AUTO** — software/cloud/front, tabela existente → roda na fila autônoma (`queue.txt`). Testável na nuvem HOJE.
> - 🟠 **MIGRATION** — precisa tabela nova → fluxo com checkpoint humano (não autônomo). Depois, endpoint vira AUTO.
> - 🔴 **HARDWARE** — precisa o Mini PC/GPU/site → `queue-hardware.txt`, roda quando você sinalizar o PC.
> Specs em `tools/agent-driver/tasks/`. Detalhe de produto em `PLATAFORMA_CENARIOS.md` e `EDGE_DEPLOYMENT_PLAN.md`.

## Já concluído / em andamento
- Fundação (monorepo, constitution, ADRs 0001–0020), harness de migrations, **driver+revisor+queue (L2)**.
- Fase 1 (schema edge). Fase 2 cloud: heartbeat(002), admin sites/tokens(003), enrollment(004), health(005),
  history(009), devices(010/011), token-mgmt(012), OpenAPI(013), sentry(014), fleet-overview(016).
- Em fila/ciclo: 017 (site detail/update), 018 (heartbeat summary).
- Infra de autonomia specada: 015 (security-clearance), 019 (auto-bounce fix), 020 (planner, dormente).
- Cenários (edição visual): 021 (harness front), 022 (API cenário), 023 (editor visual).

## 🟢 AUTO — rodam na fila autônoma (testáveis na nuvem hoje)
| ID | Task | Depende de |
|----|------|-----------|
| 017 | Site detail + update | — |
| 018 | Heartbeat summary | — |
| 021 | Harness de teste de front (Vitest+RTL+Playwright+CI) | — |
| 022 | API de cenário (leitura) + catálogo operation-types | — |
| 023 | Editor visual de cenário (front) | 021, 022 |
| 024 | Escrita de cenário + 3 operation-types (epi_zone, defect_trigger, counting_line) | 022 |
| 025 | Model rollout/version-pin API (manifesto + pin por tenant×módulo) | — |
| 026 | Front: painel "Sites & Saúde" + fleet overview (UI) | 021 |
| 027 | Harness D2: synthetic RTSP + cenários baseline/isolamento (sem GPU) | — |
| 028 | edge-sync-agent: core lógico (buffer SQLite, uploader+backoff, config poller) testável com mocks | — |

## 🟠 MIGRATION — checkpoint humano (cria tabela; depois o endpoint vira AUTO)
| ID | Task | Tabela nova |
|----|------|-------------|
| 029 | Events batch ingest (Fase 2) — migration + endpoint idempotente (X-Batch-Id) | `edge_events` |
| 030 | Command queue (O3) — migration + API de comandos + polling do edge | `edge_commands` |
| 031 | Gateway mgmt (O2/MikroTik) — migration + API de site_gateways | `site_gateways` |

## 🔴 HARDWARE — precisam do Mini PC (rodar quando você sinalizar o PC)
| ID | Task | Fase |
|----|------|------|
| 032 | DeepStream pipelines EPI/Quality/Counting + TensorRT INT8 + calibração | 5 |
| 033 | Edge stack plug-and-play (compose/install.sh/nvidia/tailscale/cloudflared/UFW + MikroTik) | 6 |
| 034 | edge-sync-agent integração real (MQTT do DeepStream, câmera real, drain offline) | 4 |
| 035 | O4 self-healing (circuit breaker GPU, supervisord) + O5 edge aplica modelo (hot-swap) | O4/O5 |
| 036 | Frontend dual-mode (fallback edge.{site}.local quando cloud cai) | 7 |
| 037 | Provisionamento RVB + Plug-and-play day (runbook on-site) | 8/10 |

## Sequência recomendada
1. **Hoje (nuvem):** terminar a fila AUTO (017→018→021→022→023→024→025→026→027→028). Isso te dá o cloud
   control plane + cenários + edge-agent lógico testáveis na nuvem.
2. **Em paralelo (checkpoint):** rodar as 3 migrations (029/030/031) pelo fluxo com gate humano; seus endpoints
   viram AUTO logo após.
3. **Quando o Mini PC chegar:** disparar `queue-hardware.txt` (032→033→034→035→036→037) — é aqui que as 3
   frentes ganham o pipeline de inferência real e o go-live fecha.

> Modelos por (tenant×módulo): EPI e pessoa (contagem) reusam base; Qualidade é custom. Eval por módulo —
> ver `PLATAFORMA_CENARIOS.md` §4. Treino/curadoria de dataset é trilha humana+dados (não task autônoma).
