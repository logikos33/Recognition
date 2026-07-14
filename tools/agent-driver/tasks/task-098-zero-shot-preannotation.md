---
title: "Onboarding: pré-anotação zero-shot (Apache — OWL-ViT/NanoOWL) para bootstrap de dataset"
pr_title: "feat(training): pré-anotação zero-shot no edge para acelerar onboarding de cliente"
commit_message: "feat(training): zero-shot pre-annotation (Apache) para bootstrap de dataset"
eval: default
risk: security
depende_de: ADR-0047
bloco: 8 (Zero-shot onboarding)
---

# Task 098 — Zero-shot pré-anotação

## Objetivo
Acelerar o onboarding de cliente novo: zero-shot pré-rotula frames → humano revisa → treina modelo custom.

## Escopo
- Integrar zero-shot Apache (ex. OWL-ViT/NanoOWL — **validar licença** antes) rodando no Jetson.
- Saída = pré-labels no formato de anotação (task-085); flag OFF por padrão (plugável, como ADR-0031/0047).
- É onboarding/pré-anotação, **não** serving de produção.

## Aceite
- [ ] Zero-shot gera pré-labels revisáveis para um cliente novo; licença do modelo confirmada Apache; flag plugável.

## Checkpoint
- STOP-for-review.
