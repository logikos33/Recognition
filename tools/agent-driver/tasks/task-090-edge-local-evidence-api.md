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

## Objetivo
Servir evidência a partir do gravador do site (LAN local) e permitir download remoto sob demanda via WireGuard.

## Escopo
- API local no edge: lista/consulta evidência do gravador; stream/download; auth de device (RS256, ADR-0019).
- Remoto: nuvem → edge (túnel) → gravador, sob demanda. Sem armazenar nos 128GB.

## Aceite
- [ ] Cliente local consulta evidência; remoto baixa sob demanda; nada persistido no edge além de buffer transitório.

## Checkpoint
- STOP-for-review. Núcleo do recorder-first.
