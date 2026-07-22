---
title: "PRIORITÁRIA: stress test dos 3 módulos JUNTOS no Jetson (RVB real) + captura de métricas de treino"
pr_title: "feat(edge): stress test cenário RVB 3-módulos + logging de métricas de treino"
commit_message: "feat(edge): stress 3 módulos (qualidade 4MP + estacionamento + EPI) + métricas de treino"
eval: manual-hardware
risk: security
requires_hardware: true
prioridade: ALTA
depende_de: ADR-0048, task-106 (config ótima), task-107 (modelos)
bloco: RVB multi-módulo
---

# Task 111 — Stress test 3 módulos + métricas de treino

## Objetivo
Estressar o Jetson com o **cenário RVB real** (28 câmeras, 3 módulos rodando JUNTOS) e capturar as **métricas de
treino** por modelo (pro futuro Training Studio). Renderizar na tela física.

## Escopo
- **Carga combinada:** 2×4MP qualidade (alta-res por ROI, o ponto crítico não medido) + 2×2MP auxiliar (rastreio) +
  8×2MP estacionamento + 16×2MP EPI. Instâncias `nvinfer` separadas por módulo (config ótima da task-106: INT8 +
  sub-batch + interval + NvDCF).
- **Medir combinado:** GPU/DLA/EMC, temps, potência, FPS/stream por módulo, drops, latência — telemetria robusta
  (task-100/campanha), JSONL etiquetado por módulo/cenário. Achar o ponto de saturação com os 3 juntos.
- **Métricas de treino (os prints do Vitor):** logar por modelo precision, recall, **mAP@0.5:0.95, mAP_small/medium/large**,
  box/cls/dfl loss, learning rate por época → base pro Training Studio (analytics de modelo na plataforma).
- Simular o gatilho da monofatura + devolução de evidência junto (overhead do loop de qualidade).

## Aceite
- [ ] 3 módulos rodando juntos (28 cams) com FPS-alvo sustentado, sem drops, folga térmica/potência; ponto de saturação registrado.
- [ ] Custo real das 2 câmeras 4MP alta-res medido. Métricas de treino logadas por modelo. Evidência na tela.

## Checkpoint
- BLOQUEADA-HARDWARE. Registrar tudo (report + doc vivo). sudo/creds = Vitor.
