---
title: "Observabilidade em tempo real do edge no Recognition (telemetria do device + métricas de app)"
pr_title: "feat(edge): telemetria do Jetson em tempo real no painel do Recognition"
commit_message: "feat(edge): observabilidade ao vivo do device (tegrastats/JPS) + métricas de app"
eval: default
risk: security
depende_de: task-034 (edge-sync-agent), task-087 (baseline), ADR-0046
relaciona: fleet-overview (016/017/018), "Sites & Saúde" (026), docs/BENCHMARK_ENGENHARIA_SOFTWARE.md (observabilidade P2)
bloco: Observabilidade (edge)
---

# Task 099 — Observabilidade em tempo real do edge no Recognition

## Objetivo
Levar a saúde do edge para dentro da plataforma, ao vivo — o que hoje só vemos por SSH/tegrastats.

## Origem dos dados (REUSAR, não reconstruir)
- **Device (Jetson):** `jetson-stats`/`jtop` (expõe o tegrastats programaticamente) ou o **Monitoring do JPS**.
  Métricas: GPU/DLA util, RAM, swap, temperaturas, consumo (VDD_IN), **throttling/clock**, disco (NVMe), uptime.
- **App:** FPS por câmera, latência de inferência, profundidade das filas Celery, status de stream (on/off), modelo ativo por câmera.

## Arquitetura
- Coletor no edge (empacota device+app em amostras) → **edge-sync-agent** → API → Redis pub/sub → **SocketIO** → painel ao vivo.
- Sem armazenar histórico pesado no edge; série temporal curta na nuvem (o suficiente pro painel).

## UI
- Estende o fleet-overview / "Sites & Saúde": card por device com **gauges ao vivo** (GPU/temp/consumo), FPS por câmera,
  alerta de throttle/disco/queda de stream. Histórico curto (sparkline).

## Disciplinas
- Multi-tenant/por-site (cross-tenant → 404). Reusar JPS Monitoring quando disponível. Não hard-codar `enP8p1s0` (ver task-095).
- Coletor no device valida on-box (hardware); plumbing API/UI testável com mock na nuvem.

## Aceite
- [ ] Painel mostra, ao vivo, telemetria real do Jetson (GPU/temp/consumo/RAM/disco) + FPS/latência por câmera; alertas de throttle/queda; tenant-scoped.

## Checkpoint
- STOP-for-review. Parte de device = validação on-box; API/UI = cloud.
