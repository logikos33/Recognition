---
title: "Recorder-first: mini-API local no edge (índice/consulta do gravador + download sob demanda via túnel)"
pr_title: "feat(edge): API local de evidência (recorder-first) com download remoto sob demanda"
commit_message: "feat(edge): mini-API local de evidência sobre o gravador"
eval: default
risk: security
depende_de: ADR-0045
bloco: 5 (Recorder-first)
---

# Task 090 — Mini-API local de evidência

> **Status:** EM REVISÃO — implementado em `agent/task-090-edge-local-evidence-api` (PR para develop; STOP-for-review, risk:security). Mini-API Flask nova em `services/edge-sync-agent/app/{evidence_api,evidence_auth,recorder_client}.py`: auth RS256 obrigatória em todo endpoint (trust-anchor keypair simétrico-invertido ao ADR-0019, ver ADR-0050), `RecorderClient` como `Protocol` com stub `InMemoryRecorderClient`/`NotConfiguredRecorderClient` (implementação ONVIF real é escopo da task-091), streaming de clipe sem cache em disco, bind-host nunca `0.0.0.0`/`::`. 111 testes verdes em `services/edge-sync-agent/tests/` (99% cobertura em `app/`), CI ganhou o step "services/edge-sync-agent tests". **Sem validação em hardware real** (Jetson/NVR) — ver seção "Security review" e ADR-0050 no PR.

## Objetivo
Servir evidência a partir do gravador do site (LAN local) e permitir download remoto sob demanda via WireGuard.

## Escopo
- API local no edge: lista/consulta evidência do gravador; stream/download; auth de device (RS256, ADR-0019).
- Remoto: nuvem → edge (túnel) → gravador, sob demanda. Sem armazenar nos 128GB.

## Aceite
- [ ] Cliente local consulta evidência; remoto baixa sob demanda; nada persistido no edge além de buffer transitório.

## Checkpoint
- STOP-for-review. Núcleo do recorder-first.
