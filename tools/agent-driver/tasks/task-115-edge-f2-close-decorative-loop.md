---
title: "F2 — Fechar o laço decorativo: runtime lê fps/threshold da config (não de env global)"
commit_message: "feat(inference): ler fps_target/threshold da config por câmera (F2)"
eval: default
risk: security
---

# F2 — Fechar o laço decorativo (FPS/threshold)

## NEEDS CLARIFICATION
Nenhuma (fonte confirmada: config entregue pelo F1, por câmera).

## Objetivo
Hoje `cameras.fps_target`/`quality_preset` e `confidence_threshold` têm banco+API+UI mas **nenhum
consumidor de runtime** — o comportamento vem de env globals (`YOLO_INFERENCE_EVERY_N_FRAMES`,
`DETECTION_CONFIDENCE_THRESHOLD`). O operador muda o FPS na UI e nada acontece.

## Critérios de aceitação
- [ ] O runtime de inferência lê `fps_target`/`confidence_threshold` **da config entregue pelo F1 (por câmera)**, com env global rebaixada a fallback default (documentado).
- [ ] **Prova (obrigatória):** mudar `fps_target` na UI → o pipeline passa a rodar naquele FPS em ≤1 ciclo de poll, provado por telemetria (heartbeat/log). **Requer o Jetson/pipeline rodando** — a evidência é gerada no box, não só no CI.
- [ ] Eval `default` verde.

## Invariantes de segurança
- Config por câmera respeita tenant/site do enrollment. Sem AGPL no caminho servido.

## Arquivos no escopo
- `services/inference/**` (leitura de config por câmera)
- `services/api/app/infrastructure/queue/tasks/inference.py` (fallback default)
- testes de unidade do caminho de leitura de config

## Frase de aceite
"O operador muda o FPS de uma câmera na UI e o pipeline no Jetson passa a rodar naquele FPS em <1 ciclo
de poll, sem SSH." (provar com telemetria no box)
