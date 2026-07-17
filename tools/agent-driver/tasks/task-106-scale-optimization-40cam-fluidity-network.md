---
title: "PRIORITÁRIA: campanha de escala/otimização — até 40 câmeras (YOLOX vs RF-DETR), fluidez das bboxes e impacto de rede"
pr_title: "feat(edge): campanha de escala 40 cams + otimização + fluidez (tracker) + impacto de rede"
commit_message: "feat(edge): stress até 40 cams, otimizações, fluidez NvDCF e rede real"
eval: manual-hardware
risk: security
requires_hardware: true
prioridade: ALTA
depende_de: task-101/102 (YOLOX), task-105 (RF-DETR), task-104 (DLA), ADR-0044
---

# Task 106 — Escala até 40 câmeras + otimização + fluidez + rede

## Objetivo
Achar o **limite SEGURO do hardware** rodando o **modelo real** (até **40 câmeras**), a **config ótima** de
performance, **corrigir a fluidez** das bounding boxes (nível do sample DeepStream), e medir o **impacto de
câmera real na rede** + o **overhead do Recognition**. Rodar **YOLOX e RF-DETR** pra bench e decisão.
**28 câmeras = demanda de produção; 40 câmeras = poder de expansão (upsell de câmeras adicionais).**

## Escopo (liberdade total pra buscar/configurar/iterar — falhar e tentar de novo)
1. **Escala:** estender o stress (102) até **40 streams**, com o **modelo real** (não só o Nano). Rodar YOLOX **e** RF-DETR.
   Achar o **limite seguro** = FPS-alvo sustentado, sem frames dropados, com folga térmica/potência (sem throttle) e
   headroom pro overhead do Recognition.
2. **Fluidez das bboxes (prioridade — hoje está ruim):** o sample DeepStream é suave porque usa **inferência em
   INTERVALO + tracker (NvDCF)** que interpola boxes entre frames. Reproduzir isso: PGIE `interval=N` + `nvtracker`
   (NvDCF) + OSD a full FPS. Investigar/consertar o jitter atual. **Bônus:** isso também é a maior otimização de escala.
3. **Otimizações (liberdade total):** batch dinâmico no export ONNX (batch-N no nvinfer), `interval` do nvinfer,
   `jetson_clocks` (clock travado), INT8 **com calibração real**, substream vs main, `streammux`/`tiler` tuning,
   **DLA** se compensar após export DLA-friendly (decode fora do grafo). Iterar até 40 cams seguras no modelo real.
4. **RF-DETR:** ler TODA a documentação do modelo (rfdetr/roboflow), buscar benchmarks que correlacionem com a
   nossa realidade (edge Orin NX, PPE, 28-40 cams). Parser DeepStream próprio (não o YOLOX/088). Treino comparável,
   DLA eval (transformer costuma ter fallback pior — caracterizar), export, stress.
5. **Impacto de rede + Recognition:** medir o que muda com **câmera real na rede** (RTSP jitter, banda, decode,
   reconexão) vs sintético; e o **overhead do sistema** (edge-sync-agent enviando eventos/telemetria, túnel
   WireGuard, evidência) rodando junto da inferência. Se fizer sentido, simular a carga completa do Recognition.

6. **Cena de ALTA DENSIDADE (carros) — teste de detecções por frame:** usar um **vídeo pesado da biblioteca de
   samples do DeepStream** (o de tráfego tem muitos carros, ex. `/opt/nvidia/deepstream/.../samples/streams/
   sample_1080p_h264.mp4`) e rodar **detecção de carro** (classe `car` do COCO — modelo COCO, não o PPE) com o
   **máximo de inferências** (interval=0, todo frame) pra ver: (a) o pico de carga com muitas boxes simultâneas,
   (b) como a **fluidez/qualidade das boxes** fica numa cena densa, na tela física. Comparar com/sem tracker+interval.
   É o cenário de pior caso de densidade — complementa o teste de "muitos streams".

7. **Saúde da ventoinha (fan):** o Power GUI mostrou **PWM 100% mas RPM 0** (profile "quiet"). Investigar:
   a fan está **realmente girando** (ou é falta de sensor tach)? Conferir `nvfancontrol`, sysfs PWM/RPM, e **setar
   um perfil térmico adequado pra carga sustentada** (não "quiet") — crítico pra 40 cams 24/7 no cliente sem throttle.
8. **Telemetria robusta (garantir dados pro gráfico depois):** o gráfico final é OUTRO prompt/etapa; AQUI a obrigação
   é **capturar dados SUFICIENTES** — todos os campos (GPU/DLA/EMC, RAM, swap, temps, potência VDD_*, CPU, **fan RPM/PWM**,
   FPS/stream, drops, latência), em intervalo adequado, **persistidos em JSONL com timestamp + label de fase/cenário**.
   Melhorar o coletor (task-100) se faltar campo. Não perder amostra em nenhum experimento — sem dado, sem gráfico.
9. **Modelos mais pesados (cenário RVB complexo):** além de YOLOX-Tiny/S e RF-DETR, testar **variantes mais pesadas**
   (YOLOX-M/L, RF-DETR S/M/L, outras libs Apache se fizer sentido) pra mapear a **curva acurácia × custo** — a RVB pode
   ser cena complexa. **Liberdade pra treinar mais modelos via API do Roboflow.** Objetivo: saber até onde o hardware
   sustenta modelo pesado nas 28/40 cams.

## Aceite (relatório)
- [ ] **Limite seguro por modelo** (YOLOX e RF-DETR): quantas câmeras no FPS-alvo, com margem térmica/potência.
- [ ] **Config ótima** documentada (interval, tracker, batch, clocks, INT8, substream, DLA) + ganho de cada alavanca.
- [ ] **Fluidez corrigida** — evidência na tela física (comparativo antes/depois), nível do sample DeepStream.
- [ ] **Bench YOLOX × RF-DETR** (treino, acurácia, inferência, 28/40 cams, DLA) → recomendação de produção.
- [ ] **Impacto de rede/Recognition** quantificado.
- [ ] Recomendação final: config de **28 (produção)** e de **40 (expansão)**.

## Disciplinas
- Seguir `docs/edge/REGRAS_PLATAFORMA_JETSON.md` (ler antes de instalar, **alimentar** com aprendizados novos).
- Detector Apache (YOLOX/RF-DETR); ZERO ultralytics/AGPL. Render na tela física. Total liberdade de busca/config.
- `sudo`/creds da câmera = Vitor (PARE e peça). PR para develop; não promover pra produção.

## Checkpoint
- BLOQUEADA-HARDWARE. Campanha iterativa (falhar/tentar). Registrar tudo (report + doc vivo).

## Limpeza pré-RVB (DIFERIDA — NÃO agora)
Ao FIM de todos os testes, ANTES de implementar na RVB, fazer uma limpa do box se necessário (artefatos de experimento, modelos/engines de teste, datasets, logs, venvs) pra liberar disco e deixar só o de produção. **Não fazer agora** — só depois da campanha. Registrar o que pode ser removido.
