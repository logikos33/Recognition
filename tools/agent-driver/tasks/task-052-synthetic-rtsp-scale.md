# Task 052 — Harness de Escala 4→28 Câmeras com RTSP Sintético

**Status**: PENDING
**Risk**: low (testes locais, sem infra produção)
**Branch**: feat/task-052-synthetic-rtsp-scale

## Objetivo

Estender o harness existente (task-027, MediaMTX) para testar escala de 4→28 câmeras
sintéticas simultâneas, coletando métricas de latência e ponto de degradação.

## Contexto

- Harness base em `tests/harness/` com `docker-compose.harness.yml` + MediaMTX
- task-027 implementou cenário baseline (1-4 câmeras, RTSP sintético via FFmpeg)
- task-053 usa métricas deste harness para dimensionar PgBouncer

## Entregáveis

- [ ] `tests/harness/scenarios/scale/generator.py` — gera N streams RTSP sintéticos no MediaMTX
- [ ] `tests/harness/scenarios/scale/runner.py` — dispara inference_loop por câmera, coleta métricas
- [ ] `tests/harness/scenarios/scale/docker-compose.scale.yml` — orquestra MediaMTX + N câmeras
- [ ] Métricas coletadas: latência p50/p95 frame→detecção, inf/s, erros de conexão, conexões PG
- [ ] `docs/evidence/e2e-scale/REPORT.md` — tabela 4/8/16/28 câmeras + ponto de degradação

## Aceite

- Sobe 4 câmeras localmente com E2E completo (RTSP→infer→det:→alert)
- Identifica ponto de degradação (latência p95 > 5s ou erro > 5%)
- Alimenta task-053 com ponto de degradação

## Dependências

- task-027 (harness-rtsp) — base implementada
- task-055a (gate de licença) — ONNX detector no caminho servido
