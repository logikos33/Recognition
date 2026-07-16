---
title: "Detector: benchmark RF-DETR vs YOLOX no Orin NX 16GB (GPU vs DLA, FP16 vs INT8, 28 câmeras) — HARDWARE"
pr_title: "docs(edge): benchmark de detector no Jetson Orin NX + escolha de default"
commit_message: "docs(edge): benchmark RF-DETR/YOLOX no Orin NX 16GB"
eval: manual-hardware
risk: security
requires_hardware: true
depende_de: ADR-0044, task-082
bloco: 2 (Detector)
---

# Task 084 — Benchmark de detector no Jetson (HARDWARE)

## Objetivo
Decidir empiricamente o default de produção: RF-DETR vs YOLOX no Orin NX 16GB, com 28 câmeras.

## Escopo
- Medir FPS/latência/precisão: RF-DETR vs YOLOX · GPU vs **DLA** · FP16 vs **INT8** · até 28 streams.
- Registrar ponto de degradação e o default recomendado por deployment.

## Aceite
- [ ] Relatório com números reais no Orin NX 16GB; default de produção definido; sem AGPL.

## Checkpoint
- BLOQUEADA-HARDWARE. Roda no box (amanhã). Fora da queue.txt autônoma.

## Benchmark parcial (2026-07-16) — YOLOX-Nano no Orin NX real

**PARCIAL, não fecha o aceite.** Mede só YOLOX-Nano (checkpoint placeholder — o modelo de
produção vem da task-086), input 416×416, batch 1, via `trtexec` (throughput da engine pura,
sem pré/pós-processamento). RF-DETR **não** medido (não há ONNX RF-DETR real no repo — só
sintético; export exige torch, adiado). Serve pra caracterizar o hardware e as tendências
precisão/device, não pra escolher o default de produção ainda.

**Contexto:** NV Power Mode **40W** (MAXN Super), governor `schedutil`, **`jetson_clocks` NÃO
travado** → há variância nos números (min « mean observado). Pra benchmark rigoroso, travar
clocks com `jetson_clocks` antes (precisa sudo — não feito nesta sessão).

| Precisão / Device | Throughput | Latência média | Nota |
|---|---|---|---|
| FP32 GPU | 195 qps | 5.32 ms | baseline |
| **FP16 GPU** | **310 qps** | **3.39 ms** | **melhor** — 1.6× FP32 |
| INT8 GPU | 233 qps | 4.47 ms | + lento que FP16 (modelo minúsculo, sem calibração real) |
| DLA (FP16, core 0) | 102 qps | 9.89 ms | 3× + lento — fallback pesado pra GPU |

**Achados:**
1. **FP16 é o sweet spot** pra YOLOX-Nano no Orin NX (310 qps, 3.4 ms).
2. **INT8 não ajuda neste modelo minúsculo** — Nano não é compute-bound, então a
   quantização só adiciona overhead. Sem calibração real (`trtexec --int8` usa ranges
   dinâmicos aleatórios), também prejudica. INT8 provavelmente só compensa num modelo maior
   (YOLOX-S/M) e **com calibração de verdade** (dataset representativo → `cal_trt.bin`).
3. **DLA não ajuda neste export ONNX** — muitos layers da cabeça do YOLOX (CONSTANT/CAST/ops
   de shape, `FLOOR_DIV`, o `Concat` do decode) são **unsupported on DLA** e caem de volta pra
   GPU (`--allowGPUFallback`), gerando round-trips GPU↔DLA que matam a performance. **Pra o DLA
   realmente descarregar a GPU** (o objetivo — rodar detector no DLA e liberar GPU pras outras
   câmeras), o modelo precisa de um **export "DLA-clean"**: cabeça de detecção simplificada,
   decode de grid/stride feito fora do grafo (no host/GPU). Fica como requisito pra task-086
   (treino/export) se DLA for parte da estratégia de escala.

**Dimensionamento (liga com task-100):** a 310 qps de FP16, um único Orin NX GPU aguentaria
28 câmeras com folga a 5 FPS/câmera (=140 inf/s « 310) e ainda a 10 FPS/câmera (=280). **Mas**
é o modelo Nano placeholder — o modelo real (task-086, provavelmente YOLOX-S ou RF-DETR) é mais
pesado, então o teto de câmeras cai proporcionalmente. Refazer com o modelo de produção +
clocks travados + calibração INT8 real antes de definir o default.

**Reprodução:** engines em `~/yolox-visual-test/*.engine` no box; logs em `bench_int8.log`,
`bench_dla.log`. Comando: `trtexec --onnx=yolox_nano.onnx --fp16|--int8|--useDLACore=0 ...`.
