---
title: "AGPL-zero: license-gate escaneia IMPORTS (não só requirements) no caminho servido"
pr_title: "feat(ci): license-gate detecta import de pacotes AGPL no código servido"
commit_message: "feat(ci): gate de licença por import, além de requirements"
eval: default
risk: security
depende_de: ADR-0043
bloco: 1 (AGPL-zero)
---

# Task 081 — License-gate por import

## Objetivo
Fechar o furo: hoje `scripts/check_license_gate.py` só olha requirements. Um `import ultralytics` em código
servido passa. O gate deve pegar isso.

## Escopo
- Estender o gate para escanear imports (AST/grep) de pacotes AGPL (`ultralytics`, ...) nos pacotes servidos
  (services/api/app, services/inference), excluindo trilhas de treino offline.
- Rodar no CI (ci.yml) como parte do license-gate.

## Aceite
- [ ] Introduzir `import ultralytics` num arquivo servido faz o CI **falhar**; caminho atual passa. Teste do gate.

## Checkpoint
- STOP-for-review. Base do Bloco 1.
