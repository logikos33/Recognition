# Experimentos Edge — Jetson Orin NX 16GB — 2026-07-16

> Sequência **103 → 104 → 101 → 102** executada no hardware real via SSH (`pandora@100.93.126.76`, Tailscale).
> Tudo observável renderizado na **tela física** do box (`DISPLAY=:1`, `XAUTHORITY=/run/user/1000/gdm/Xauthority`).
> Detector servido = ONNX **Apache 2.0 (YOLOX)**. Zero ultralytics/AGPL no caminho servido.

## ⚠️ Divergência de premissa registrada (C-04)

As tasks formais **101, 102, 103, 104** e os docs `docs/edge/PLANEJAMENTO_EXPERIMENTOS_EDGE.md` /
`STATUS_2026-07-16_jetson_handson.md` **não existem** em nenhuma branch do repo (a maior task é a 098)
nem no box. A sequência foi executada usando a **especificação auto-contida do prompt** como autoridade
e o **estado real do box** como verdade de campo (C-04: validar o real, não confiar em arquivo/memória).
Os artefatos da sessão hands-on de 2026-07-16 (parser 088, telemetria 100, engines YOLOX, benches DLA)
**existem e estão íntegros** no box — foi a partir deles que a prontidão foi comprovada.

---

## TASK 103 — Prontidão (GO/NO-GO) — ✅ GO CONDICIONAL

Host `Pandora` · monitor HDMI 1920×1080 em `:1`.

| Item | Status | Evidência |
|---|---|---|
| Stack CUDA/TRT/DeepStream | ✅ | JetPack **6.2.1** / L4T R36.4.3 · CUDA **12.6** · TensorRT **10.3.0.30** · DeepStream **7.1** |
| GPU tooling | ✅ | `tegrastats`, `nvpmodel`, `jetson_clocks` presentes · Power **40W** · Docker 29.6.1 |
| Disco | ✅ | 88 GB livres (21% de 116 GB NVMe) |
| Parser YOLOX (088) | ✅ | `libnvdsparsebbox_yolox.so` carrega e roda — *App run successful*, **222 FPS**, 1443 detecções KITTI |
| Telemetria (100) | ✅ | `edge-telemetry-collector.service` **ativo** · `tegrastats --interval 5000` · JSONL em `~/edge-telemetry` |
| Sessão gráfica :1 | ✅ | x11 ativa (seat0/tty2) · `XAUTHORITY` ok · janela on-screen confirmada (xwininfo + screenshot) |
| Registry de engines | ✅ | `yolox_nano` onnx + fp32/fp16/int8/DLA em `~/yolox-visual-test` |
| Env de treino (101) | ❌ | **Não instalado**: sem torch-for-Jetson, sem repo YOLOX. Único venv é inference-only (tensorrt/onnxruntime/pycuda). Índice `pypi.jetson-ai-lab.dev` **inacessível** (HTTP 000); `download.pytorch.org` OK (200). `libopenblas` ausente. |
| RTSP sintético (052, p/ 102) | ⚠️ | `gst-launch-1.0` presente; **ffmpeg e mediamtx ausentes**. |
| jetson_clocks max-perf | ⚠️ | `jetson_clocks --show` exige **sudo** (senha = Vitor). |
| Roboflow API key (101) | ⛔ | **Passo do Vitor**. |
| Creds câmera Intelbras (102) | ⛔ | **Passo do Vitor**. |

**Veredito:** GO para avançar à 104 (sem gates). 101 e 102 bloqueadas até liberação do Vitor.

Screenshot: `~/jetson-experiments/artifacts/task103_screen.png`.

---

## TASK 104 — DLA (bloqueante do stress) — ✅ DECISÃO: GPU-ONLY

Caracterização feita sobre o **proxy `yolox_nano`** (o modelo real virá da 101).

**Toolchain:** ✅ `trtexec --useDLACore=N --allowGPUFallback` disponível (TensorRT 10.3, 2 DLA cores no Orin NX).

**DLA-clean — IMPOSSÍVEL neste grafo.** Build com `--useDLACore=0` **sem** `--allowGPUFallback` falha:
> `Error Code 2: Internal Error (Assertion allowGPUFallback failed. Layer '644' is not supported on DLA but GPU fallback is not enabled.)` → `DLA validation failed`

**Camadas que caem para GPU (113 no total):** 83 `CONSTANT` · 16 `CAST` · 8 `ELEMENTWISE` · 4 `SHUFFLE` · 2 `POOLING`.
São os ops de **decode/grid da cabeça YOLOX**, não a espinha convolucional.

**Benchmark justo (mesma precisão fp16), trtexec:**

| Caminho | Throughput | Latência média |
|---|---|---|
| **GPU-only fp16** | **465 qps** | **2.30 ms** |
| DLA + GPU fallback (fp16) | 103 qps | 9.89 ms |

DLA-augmented é **~4.5× mais lento** por stream — o ping-pong DLA↔GPU nas 113 camadas de fallback
anula o offload.

**Decisão:** o stress (102) roda **GPU-only** primeiro. **Reavaliar DLA após a 101**, quando houver o
modelo real com export DLA-friendly (decode fora do grafo, deixando só conv/bn/act para o DLA).

Logs: `~/jetson-experiments/logs/dla_clean_attempt.log`, `bench_gpu_fp16.log`; bench DLA prévio em
`~/yolox-visual-test/bench_dla.log`. Screenshot: `~/jetson-experiments/artifacts/task104_screen.png`.

---

## TASK 101 — Tempo de treino — ⛔ BLOQUEADA (aguarda Vitor)

Pendências para desbloquear:
1. **Roboflow API key** do dataset *"PPE Dataset for Workplace Safety"* (SiaBar), export COCO.
2. **Env de treino**: torch-for-Jetson (JP6.2/CUDA12.6, download grande) + `libopenblas` (apt/sudo) + repo YOLOX (Apache).
   Alternativa sem sudo no host: container NGC `l4t-pytorch` (Docker já instalado).

## TASK 102 — Stress 28 câmeras — ⛔ BLOQUEADA (aguarda Vitor)

Pendências:
1. **Creds/RTSP da câmera Intelbras real** (passo 0).
2. **RTSP sintético (052)**: instalar `ffmpeg` (sudo) e/ou `mediamtx` (binário, download) — MediaMTX é o padrão de produção (ADR-0009).
3. **jetson_clocks max** (sudo) para medição de teto de performance.

---

*Registrado por Claude Code · sequência edge · 2026-07-16.*
