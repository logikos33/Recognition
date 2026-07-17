---
title: "PRÉ-TESTE (bloqueante): validação de prontidão do Jetson — tudo que o projeto precisa está no box?"
pr_title: "chore(edge): checklist de prontidão do Jetson antes dos experimentos"
commit_message: "chore(edge): pré-flight de prontidão do box (GO/NO-GO)"
eval: manual-hardware
risk: security
requires_hardware: true
prioridade: ALTA (roda ANTES de 104/101/102)
depende_de: task-087 (baseline)
---

# Task 103 — Prontidão do Jetson (GO/NO-GO antes dos testes)

## Objetivo
Antes de qualquer experimento (104/101/102), **validar que o box tem TUDO** que o projeto precisa. Se faltar,
**corrigir antes** de testar. Sem GO, não iniciar os experimentos. Roda via SSH em `pandora@100.93.126.76`.

## Checklist (validar cada item; reportar ✅/❌ + fix do gap)
- **Stack base:** JetPack 6.2 · CUDA 12.6 · cuDNN 9.3 · TensorRT 10.3 · DeepStream 7.1 (reconfirmar `--version-all`).
- **Parser YOLOX custom (task-088):** compila e carrega no `nvinfer` (config de teste).
- **Telemetria (task-100):** instalada como `systemctl --user`, rodando, gravando JSONL.
- **Env de treino:** PyTorch-for-Jetson (wheel compatível JetPack 6.2/CUDA 12.6) + repo **YOLOX (Apache)** instaláveis. ZERO ultralytics.
- **RTSP sintético (task-052 harness):** presente e roda sem GPU.
- **Sessão gráfica:** `DISPLAY=:1` + `XAUTHORITY=/run/user/1000/gdm/Xauthority` acessível pra renderizar na tela.
- **Disco:** NVMe com espaço pra dataset + engines (checar `df -h`).
- **Modelo/registry:** como o box obtém o modelo (local vs registry) definido.
- **Acesso/segredos:** SSH por chave OK; mapear os pontos que exigem **senha sudo** ou **API key** (Roboflow) → precisam do Vitor.

## Aceite
- [ ] Relatório **GO/NO-GO** com cada item ✅/❌ e o fix aplicado dos gaps. Só com GO seguem 104/101/102.

## Checkpoint
- BLOQUEANTE. Corrigir gaps antes de testar. Hardware.
