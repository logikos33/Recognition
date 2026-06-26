---
title: "DeepStream pipelines EPI/Quality/Counting + TensorRT INT8 (Fase 5)"
pr_title: "feat(edge): pipelines DeepStream EPI/Quality/Counting + TensorRT INT8"
commit_message: "feat(edge): 3 pipelines DeepStream (EPI/Quality/Counting) com TensorRT INT8 na GPU"
eval: manual-hardware
budget_minutes: 120
risk: security
requires_hardware: true
status: BLOQUEADA-HARDWARE — rodar SÓ quando o Mini PC (RTX) estiver disponível. Fora da queue.txt autônoma.
---

# Tarefa 032 — Pipelines DeepStream (Fase 5) · BLOQUEADA-HARDWARE

> 🔴 Precisa do Mini PC + RTX. Não roda/valida na nuvem. Disparar via `queue-hardware.txt` quando o PC chegar.

## Objetivo
Os 3 pipelines de inferência de borda das frentes da RVB, na GPU: EPI (detecção PPE), Qualidade (defeito +
OCR + contagem única) e Counting/Estacionamento (pessoa + DeepSORT + linha). TensorRT INT8 + calibração.
Lê a `config` do cenário por câmera (task-024). Publica detecções no Redis local / MQTT (padrão da arquitetura).

## Depende de
- Mini PC provisionado (033), edge-sync-agent (028+034), operation-types (024), modelos por módulo (trilha de dados).

## Escopo (expandir ao desbloquear, com o PC em mãos)
- 3 pipelines no DeepStream multi-pipeline (batch por módulo); TensorRT INT8 + calibração; aplica ROI/linha/classes do cenário.
- Counting via DeepSORT (track único) + cruzamento de linha; EPI por zona; Qualidade por gatilho + OCR.
- Validar FPS/latência por câmera; GPU < limite; zero frame drop em janela; circuit breaker (035).

## Eval (manual-hardware)
- Cenários da Fase 9 com GPU real: baseline 28 câmeras, carga, latência < alvo. Validação humana no PC (não CI).

## Critérios de aceitação
- [ ] 3 pipelines processando as câmeras da RVB na GPU, lendo o cenário; métricas dentro do alvo; validado no PC.

## Checkpoint
- HARDWARE. Validação humana no PC. Não auto-merge; revisão + teste no equipamento.
