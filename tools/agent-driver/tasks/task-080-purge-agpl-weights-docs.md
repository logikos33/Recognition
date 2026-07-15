---
title: "AGPL-zero: remover yolov8n.pt do repo e limpar docs/env (INFERENCE_ENGINE=ultralytics)"
pr_title: "chore(license): remover pesos AGPL e referências a ultralytics nas docs/env"
commit_message: "chore(license): purga yolov8n.pt + limpa docs/env do caminho ultralytics"
eval: default
risk: security
depende_de: ADR-0043, task-079
bloco: 1 (AGPL-zero)
---

# Task 080 — Purga de pesos AGPL + limpeza de docs/env

**Status**: PR aberto (branch `agent/task-080-purge-agpl-weights-docs`).

## Objetivo
Tirar do repositório os pesos AGPL e as referências que induzem ao caminho ultralytics.

## Escopo (confirmado — C-04)
- Remover `yolov8n.pt` (e `yolov8n.onnx` se derivado de pesos AGPL) da raiz do repo.
- Limpar `services/inference/AGENT.md`, `inference/AGENTS.md`, `.env.example` e demais que citam
  `INFERENCE_ENGINE=ultralytics` / `YOLO_MODEL_PATH=yolov8n.pt` como caminho válido.
- Atualizar `THIRD_PARTY_NOTICES.txt` e o README (nota de licença) refletindo o caminho 100% Apache.

## Aceite
- [x] Imports AGPL no caminho servido = 0 (gate por import da task-081 com `KNOWN_IMPORT_EXCEPTIONS`
  agora VAZIA — `ultralytics_compat.py` removido, backend legado da factory removido com ValueError
  dedicado); pesos AGPL fora do repo (raiz nunca esteve trackeada — ver correção abaixo — e agora está
  no `.gitignore`); docs coerentes (`.env.example`, `services/inference/AGENT.md`,
  `services/inference/inference/AGENTS.md`, `AGENTS.md`, README).

## Correções de premissa (C-04 — estado real vs spec)
1. **`yolov8n.pt`/`yolov8n.onnx` da raiz NUNCA estiveram commitados** — são arquivos locais untracked
   do checkout de trabalho. O ADR-0043 afirma "o peso AGPL yolov8n.pt está commitado na raiz": falso no
   git. Ação real: entradas no `.gitignore` para nunca entrarem.
2. **ACHADO NOVO — peso AGPL trackeado de verdade:** `apps/landing/public/models/yolov8n-demo.onnx`
   (12MB, derivado de pesos ultralytics AGPL, distribuído publicamente pela demo da landing page —
   `DemoCamera.tsx`). NÃO removido nesta task: quebraria a demo pública com mensagem enganosa ("verifique
   sua conexão") — é decisão de produto (trocar por YOLOX-nano ONNX Apache re-exportado, ou desativar a
   demo). `.gitkeep` do diretório atualizado com o aviso; decisão fica com o Vitor (reportada no resumo
   do Bloco 1).
3. `ULTRALYTICS_HUB_*` no `.env.example`: anotado como LEGADO (dispatch de treino via Hub produz modelos
   derivados de AGPL) — remoção do código na task-086, não aqui (mexer no fluxo de treino é escopo dela).
4. `grep -ri ultralytics = 0` literal é inalcançável e não é o objetivo: sobram menções em comentários/
   docstrings explicando a migração e o client REST `infrastructure/hub/ultralytics_hub.py` (HTTP puro,
   sem código AGPL — sai na task-086). O aceite real = zero IMPORTS AGPL (gate da task-081 cobre).

## Checkpoint
- STOP-for-review. Depende de 079 (código de Qualidade já portado).
