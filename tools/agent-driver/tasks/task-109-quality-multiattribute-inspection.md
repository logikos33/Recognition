---
title: "Qualidade: inspeção multi-atributo por ROI + etapas + rastreio/cronômetro (2×4MP principal + 2×2MP auxiliar)"
pr_title: "feat(quality): inspeção multi-atributo por ROI, etapas e cronômetro de ciclo"
commit_message: "feat(quality): pontos de atenção por ROI + etapas + tempo de ciclo"
eval: default
risk: security
depende_de: ADR-0048, task-107, task-108
bloco: RVB multi-módulo
---

# Task 109 — Inspeção de qualidade multi-atributo

## Objetivo
Inspecionar os **pontos de atenção** da peça (vedação, isolamento, …) em alta-res, por etapa, com rastreio e cronômetro.

## Escopo
- **Principais (4MP):** inferência **por ROI** nos pontos de atenção (não frame inteiro) → OK/falha por atributo.
- **Auxiliares (2MP):** rastrear a peça (NvDCF) e **cronometrar cada etapa** do processo.
- Modelo de dados da **sessão de inspeção**: peça (ID) → etapas → atributos (OK/falha) → tempo → evidências.
- **Pontos de atenção = input do cliente** (a preencher: viram as classes/ROIs). Config na UI (operation-type defect_trigger).

## Aceite
- [ ] Dado o gatilho (108), a peça é rastreada, cronometrada e cada ponto de atenção avaliado OK/falha por etapa; resultado consolidado por peça.

## Checkpoint
- STOP-for-review. Lista de pontos de atenção pendente do cliente.
