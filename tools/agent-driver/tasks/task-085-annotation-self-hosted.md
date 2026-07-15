---
title: "Treino LGPD-clean: anotação self-hosted (CVAT/Label Studio) integrada ao dataset"
pr_title: "feat(training): anotação self-hosted on-prem (sem enviar imagem a terceiro)"
commit_message: "feat(training): integração de anotação self-hosted para datasets"
eval: default
risk: security
depende_de: ADR-0047
bloco: 3 (Treino LGPD-clean)
---

# Task 085 — Anotação self-hosted

## Objetivo
Anotar datasets sem mandar imagem de trabalhador pra SaaS (LGPD). CVAT ou Label Studio on-prem.

## Escopo
- Escolher CVAT vs Label Studio; integração import/export COCO com o versionamento de dataset atual.
- Fluxo: frames (câmera/NVR/upload) → anotação on-prem → dataset versionado.

## Aceite
- [ ] Ciclo de anotação → dataset COCO versionado sem terceiro; documentado.

## Checkpoint
- STOP-for-review. Coerente com docs/security/LGPD_PRIVACIDADE_CFTV.md.
