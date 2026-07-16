# Status — Sessão hands-on Jetson Orin NX (2026-07-16)

Registro do que foi feito, validado e o que ficou bloqueado numa sessão remota
(SSH via Tailscale) no box de produção do edge da RVB. Complementa
`EDGE_DEPLOYMENT_PLAN.md` e as tasks 084/087/088/095/096/100.

**Box:** NVIDIA Jetson Orin NX Super 16GB (Palit Pandora A002FV1P1), hostname
`pandora`. JetPack 6.2 / L4T r36.4.3 / Ubuntu 22.04 / kernel 5.15.148-tegra.
DeepStream 7.1 · CUDA 12.6 · TensorRT 10.3 · cuDNN 9.0. Power mode 40W (MAXN Super).

---

## Acesso (destravado nesta sessão)

- **SSH autônomo por chave:** `ssh pandora@100.93.126.76` (IP Tailscale). A chave
  pública da estação foi instalada em `~/.ssh/authorized_keys` do `pandora` — antes
  só havia acesso por senha. LAN de bancada: `192.168.1.66/24`, NIC `enP8p1s0`.
- **`sudo` ainda exige senha** (sem passwordless) — `apt install` etc. exigem alguém
  digitando a senha interativamente; a automação não contorna isso.
- **Sessão gráfica física:** monitor HDMI (Dell E2222HS), X11 em `:1`,
  `XAUTHORITY=/run/user/1000/gdm/Xauthority` — usada pra demos visuais na tela.
- **Timezone/NTP já corretos** (`America/Sao_Paulo`, sincronizado) — o TODO da
  task-087 sobre relógio errado não se aplica mais.

---

## Status por task

| Task | Título | Estado | Nota |
|---|---|---|---|
| 100 | Observabilidade MVP + baseline | ✅ **avançada** | coletor systemd rodando; datasets idle/inference capturados; falta só o ingest cloud (device precisa enrolar) |
| 084 | Benchmark detector Orin | ✅ **parcial** | YOLOX-Nano caracterizado (FP16/FP32/INT8/DLA); falta modelo real + RF-DETR |
| 088 | Pipelines DeepStream | ✅ **desbloqueada** (parser) | custom parser YOLOX escrito/validado; falta modelo real, RF-DETR, Redis, EPI+Contagem |
| 087 | Baseline JetPack | ✅ SDK/stack confirmados | SSH+timezone resolvidos; falta `install.sh` plug-and-play |
| 096 | Descoberta ONVIF | ⏳ **inconclusiva** | código validado na rede real; câmera não responde (ONVIF-off de fábrica) |
| 095 | Portabilidade de rede | 🔴 **bloqueada** | sem MikroTik conectado, sem WireGuard configurado |
| 034 | edge-sync-agent real | 🔴 **bloqueada** | precisa do pipeline DeepStream de produção + câmera |
| 089 | Integração VST | 🔴 **bloqueada** | hardware/JPS |

---

## O que foi validado (com evidência)

### Stack de inferência funciona ponta a ponta no hardware real
- **DeepStream sample** (TrafficCamNet, config do SDK): 4 streams @ ~30 FPS,
  decode NVDEC + engine INT8 (build on-device de ONNX+calibração) + tracker NvDCF,
  renderizado ao vivo no monitor físico. `App run successful`.
- Confirma que o hardware/stack (DeepStream 7.1 + TensorRT 10.3 + CUDA 12.6 + NVDEC)
  está pronto pra pipeline de produção.

### task-100 — telemetria device-side
- Coletor reescrito como **`systemctl --user` service** (`services/edge-sync-agent/
  app/telemetry/`), substituindo o coletor `nohup` (que não sobrevivia a reboot).
  `loginctl enable-linger` habilitado **sem sudo** → sobrevive a reboot sem root.
- **Bug real corrigido:** o `tegrastats` deste JetPack emite rótulos de temperatura
  em minúsculas (`cpu@`/`gpu@`/`tj@`) — o parser normaliza; sem isso `gpu_temp_c`
  pegava o valor errado e `cpu_temp_c` vinha `None`. 20 testes offline + regressão
  com linha real do box.
- **Dataset idle × inference** (base de dimensionamento):

  | Fase | GPU | Temp GPU | Potência |
  |---|---|---|---|
  | Idle | 0% | ~40-44°C | ~4.3W |
  | Inference (YOLOX TensorRT) | 63% avg | 52-55°C | ~13W (≈3× idle) |

### task-084 — benchmark (YOLOX-Nano, `trtexec`, modo 40W)

| Precisão/Device | Throughput | Latência | Nota |
|---|---|---|---|
| **FP16 GPU** | **310 qps** | 3.4 ms | melhor |
| INT8 GPU | 233 qps | 4.5 ms | não ajuda modelo pequeno sem calibração |
| FP32 GPU | 195 qps | 5.3 ms | baseline |
| DLA FP16 | 102 qps | 9.9 ms | fallback pesado (cabeça YOLOX com ops unsupported) |

Achados: FP16 é o sweet spot; **DLA só descarrega a GPU com export "DLA-clean"**;
dimensionamento a 310 qps aguenta 28 câmeras a 5-10 FPS **com folga** — mas é o
modelo Nano placeholder (o real, task-086, é mais pesado).

### task-088 — custom bbox parser DeepStream (o gap estrutural)
- `deepstream/shared/custom_parsers/nvdsparsebbox_yolox.cpp` — o parser que faltava
  pro `nvinfer` nativo decodificar a saída raw do YOLOX (o SDK só traz sample via
  Triton). Port linha-a-linha do `_decode_positions` do código de produção.
- **Validado:** compila, carrega no `nvinfer`, é invocado, decodifica os anchors e
  produz bboxes válidas — com threshold 0.0, **1443/1443 frames** produziram caixas
  com coords corretas reescaladas pro frame, @ ~222 FPS, sem crash.

---

## Bloqueios e pendências

- **Checkpoint YOLOX público quebrado:** os únicos `.onnx` baixáveis sem torch
  (Megvii 2021) têm objectness anormal (~0.0004 → score ~0). Não bloqueia estrutura
  (parser/engine/pipeline provados), mas **impede validação de "detecta de verdade"**
  até a task-086 gerar um modelo próprio. Causa raiz não isolada (não é FP16, não é
  ordem de canal, não é normalização).
- **RF-DETR não testado com peso real:** só ONNX sintético (export real exige torch).
  Falta o parser DeepStream equivalente pra RF-DETR (saída DETR, decode diferente).
- **Câmera (task-096):** `192.168.1.8` responde ping mas não abre porta nem ONVIF —
  provável ONVIF desligado de fábrica. Revalidar com ONVIF habilitado.
- **Rede (task-095):** sem MikroTik/WireGuard no box — nada a implementar sem o
  hardware de rede + decisão de topologia do site.

---

## Artefatos

**No repo (esta branch/PR):**
- `services/edge-sync-agent/app/telemetry/` — coletor (parser/collector/entrypoint) + testes.
- `services/edge-sync-agent/deploy/edge-telemetry-collector.service` + `.env.example`.
- `deepstream/shared/custom_parsers/` — parser YOLOX + Makefile + template + README.
- `docs/runbooks/edge-telemetry-collector.md` — instalação no box.
- Achados inline nas tasks 084/087/088/096/100.

**No box (`pandora`, não versionado):**
- `~/recognition-edge-telemetry/` — coletor deployado + serviço systemd (ativo).
- `~/edge-telemetry/*.jsonl|.log` — datasets de telemetria (idle 15h preservado + inference).
- `~/yolox-visual-test/` — engines TensorRT (FP16/FP32/INT8/DLA) + demos + venv isolada.
- `~/yolox-deepstream-parser/` — parser compilado + configs de teste + kitti_out.
- `~/deepstream-smoke-test/`, `~/rfdetr-smoke-test/`, `~/onvif-validation/` — scaffolding de teste.

---

## Próximos passos

1. **task-086** gerar modelo YOLOX/RF-DETR próprio → revalidar detecção real (parser + benchmark).
2. **Parser RF-DETR** pro DeepStream (quando RF-DETR for candidato a default — ver task-084).
3. **task-100 cloud:** enrolar o device (RS256, task-097) → ligar o `HeartbeatSink` → telemetria no dashboard.
4. **task-096:** revalidar com câmera de ONVIF habilitado.
5. **task-095/034:** quando MikroTik + câmera de produção existirem no site.
6. **Higiene:** esta branch acumulou trabalho de várias tasks (100/084/088) — considerar
   separar em PRs por task na revisão, se preferir granularidade.
