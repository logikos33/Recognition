---
title: "Recorder-first: R2 vira upload SELETIVO/diferido para dataset (não toda evidência)"
pr_title: "feat(storage): upload seletivo para R2 (flywheel de dataset), não evidência em tempo real"
commit_message: "feat(storage): R2 seletivo para dataset; evidência fica no gravador"
eval: default
risk: security
depende_de: ADR-0045
bloco: 5 (Recorder-first)
---

# Task 092 — R2 seletivo para dataset

## Objetivo
Parar de empurrar toda evidência pro R2; subir só o que alimenta o flywheel de dataset da Logikos, de forma diferida.

## Escopo
- Política de seleção (amostragem/curadoria) do que vai pro R2; upload diferido (não por evento).
- Ajustar o edge-sync-agent para o novo alvo (dataset, não evidência).

## Aceite
- [ ] Evidência não vai mais em massa pro R2; upload seletivo comprovado; custo de nuvem reduzido.

## Checkpoint
- STOP-for-review.
