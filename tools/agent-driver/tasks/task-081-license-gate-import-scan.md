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

**Status**: PR aberto (branch `agent/task-081-license-gate-import-scan`) — ver PR para número.

## Objetivo
Fechar o furo: hoje `scripts/check_license_gate.py` só olha requirements. Um `import ultralytics` em código
servido passa. O gate deve pegar isso.

## Escopo
- Estender o gate para escanear imports (AST/grep) de pacotes AGPL (`ultralytics`, ...) nos pacotes servidos
  (services/api/app, services/inference), excluindo trilhas de treino offline.
- Rodar no CI (ci.yml) como parte do license-gate.

## Aceite
- [x] Introduzir `import ultralytics` num arquivo servido faz o CI **falhar**; caminho atual passa. Teste do gate.
  (`services/api/tests/unit/test_license_gate_import_scan.py`; falha-antes/passa-depois verificado localmente
  antes do PR.)

## Nota de implementação
O scan por AST (`_check_source_imports`) cobre `services/api/app` e `services/inference/inference`. No dia em
que o scanner entrou em vigor já existiam 3 imports reais de `ultralytics` no caminho servido (achado que
motivou esta task): `quality_inference.py`, `quality_training.py` (ambos — task-079 remove) e
`domain/detectors/ultralytics_compat.py` (fallback legado do backend EPI — task-080 remove). Em vez de deixar
o gate quebrado até essas duas tasks terminarem, os 3 arquivos entraram em `KNOWN_IMPORT_EXCEPTIONS` — uma
allowlist explícita, datada e testada (`test_known_import_exceptions_all_still_exist_and_import_ultralytics`
falha se a entrada virar obsoleta, cobrando a remoção). Qualquer import AGPL **novo** fora dessa lista quebra
o CI imediatamente — é exatamente o gap que esta task fecha.

## Checkpoint
- STOP-for-review. Base do Bloco 1.
