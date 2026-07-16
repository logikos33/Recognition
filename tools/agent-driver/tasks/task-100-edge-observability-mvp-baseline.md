---
title: "PRIORITÁRIA: MVP de observabilidade do edge no Recognition + estudo baseline (idle x inferência)"
pr_title: "feat(edge): MVP telemetria do Jetson no Recognition + captura baseline idle/inferência"
commit_message: "feat(edge): observabilidade MVP do edge + dataset baseline idle vs inferência"
eval: default
risk: security
prioridade: ALTA (começar a observar já)
depende_de: task-087 (baseline), ADR-0046
relaciona: task-099 (observabilidade produtizada — este é o MVP rápido), task-034 (edge-sync)
bloco: Observabilidade (edge)
---

# Task 100 — MVP observabilidade do edge + estudo baseline (PRIORITÁRIA)

## Objetivo
Conectar o Jetson ao Recognition e mostrar a telemetria dele em **gráfico**, para acompanhar o comportamento
com o box **ligado sem inferência** (noite inteira) e depois **com inferência**. Os dois datasets viram
**estudo para dimensionar novas operações** (consumo, térmica, headroom de GPU/RAM por carga).

## Escopo mínimo (MVP — não é a versão completa da task-099)
1. **Coletor no edge:** amostra periódica (1–5s) de `tegrastats`/jetson-stats: GPU (GR3D), RAM, swap,
   temperaturas, consumo (VDD_IN), CPU, disco. Cada amostra com **timestamp** e um campo **`phase`** (`idle`|`inference`).
2. **Ingest simples no Recognition:** endpoint que recebe as amostras do device (tenant/site-scoped) e persiste
   série temporal curta.
3. **Gráfico:** painel com linhas (GPU/temp/consumo/RAM) ao longo do tempo, filtrável por `phase`, para comparar
   idle × inferência lado a lado.

## Captura JÁ (interino, enquanto o ingest não existe)
- Rodar um **logger local** no Jetson gravando `tegrastats` com timestamp num arquivo (sobrevive ao logout),
  para **não perder a noite de baseline idle**. Depois, importar esse log no ingest para o gráfico.
- Marcar a fase: hoje = `idle` (sem inferência); quando ligarmos o pipeline (task-088), = `inference`.

## Aceite
- [x] Dataset **idle** capturado (sessão 2026-07-15, coletor nohup, 15h contínuas — ver abaixo).
- [x] Dataset **inference** comparável capturado (sessão 2026-07-16, carga real TensorRT/YOLOX, 33 amostras).
- [x] Base para estudo de dimensionamento (headroom por carga) documentada — ver tabela abaixo.
- [ ] Telemetria do Jetson visível em gráfico no Recognition, tenant/site-scoped — **cloud plumbing (`AdminObservabilityPage`,
      `observability_routes.py`, migrations 088/089) já está em `develop`** (mergeada em sessão anterior); falta só o
      coletor enviar heartbeat de verdade (device precisa estar enrolado — RS256, task-097). Sink de heartbeat já
      existe no código do coletor (`HeartbeatSink`), desligado até o enrollment acontecer.

## Checkpoint
- STOP-for-review. Coletor no device valida on-box; ingest/UI cloud. Não hard-codar NIC (ver task-095).

## Captura iniciada (2026-07-15 21:53)
- Coletor idle rodando no box: `tegrastats --interval 5000 --logfile ~/edge-telemetry/idle_<ts>.log` (nohup, PID 3420).
- Baseline idle: GPU 0%, ~1.2GB/16GB RAM, ~40-44°C, VDD_IN ~4.3W.
- CAVEAT: nohup sobrevive logout, NÃO sobrevive reboot → para robustez futura, virar serviço systemd.
- Próximo: encerrar idle (`kill`), iniciar log `inference` ao ligar o pipeline (088); ingest+gráfico no Recognition = escopo desta task.

## Sessão 2026-07-16 — coletor systemd + dataset idle/inference real

**SSH destravado:** chave instalada em `~/.ssh/authorized_keys` do `pandora`; acesso autônomo confirmado
(`ssh pandora@100.93.126.76`, Tailscale). Timezone/NTP já corretos (`America/Sao_Paulo`, sincronizado) —
o TODO da task-087 sobre relógio errado **não se aplica mais**.

**Coletor reescrito como `systemctl --user` service** (não precisou de sudo/root):
- Código: `services/edge-sync-agent/app/telemetry/` (`tegrastats_parser.py`, `collector.py`, `__main__.py`) —
  este commit. Parser stdlib-only, defensivo, 20 testes unitários offline.
- **Bug real encontrado e corrigido**: esta versão do `tegrastats` (JetPack 6.2, no box) emite rótulos de
  temperatura em **minúsculas** (`cpu@`/`gpu@`/`tj@`), diferente do exemplo em maiúsculas usado nos fixtures
  sintéticos originais. Sem normalizar, `gpu_temp_c` caía no fallback `tj` (valor errado) e `cpu_temp_c` sempre
  vinha `None` — corrompia silenciosamente o dataset. Fix + regressão com linha real capturada do box.
- **`loginctl enable-linger pandora`** habilitado **sem sudo** (usuário pode habilitar linger pra si mesmo) →
  o serviço `systemctl --user` sobrevive a reboot sem precisar de root. Mais limpo que a unit `/etc/systemd/system`
  do plano original.
- Deploy no box: `~/recognition-edge-telemetry/` (código) + `~/.config/systemd/user/edge-telemetry-collector.service`.
- Coletor nohup antigo (PID 3420, 15h rodando) **encerrado** — log preservado em `~/edge-telemetry/idle_20260715_215309.log`.

**Dataset idle vs. inference (comparação real, tabela de dimensionamento):**

| Fase | Amostras | GPU % (avg/max) | Temp GPU | Potência (VDD_IN) |
|---|---|---|---|---|
| Idle (sessão anterior, limpo) | 15h contínuas | 0% | ~40-44°C | ~4.3W |
| Inference (YOLOX-Nano TensorRT FP16, 416×416) | 33 | 63% / 92% | 52-55°C | avg 13.0W (~3× idle) |

**CAVEAT metodológico (pra quem repetir a captura):** o arquivo `idle_*.jsonl` iniciado nesta sessão às 16:07
ficou **contaminado** — ele rodou capturando durante TODO o resto da sessão (DeepStream, builds de TensorRT,
testes RF-DETR/YOLOX), então não é idle de verdade (avg gpu_pct chegou a 39%, max 99%). **Sempre trocar
`EDGE_TELEMETRY_PHASE` no env (`~/recognition-edge-telemetry/edge-telemetry.env`) e reiniciar o serviço
(`systemctl --user restart edge-telemetry-collector`) ANTES de começar qualquer teste de carga.** Um dataset
idle pós-uso limpo foi reiniciado ao final da sessão (`idle_20260716T182356Z.jsonl`) — ainda esfriando do uso
anterior no momento do encerramento, não é baseline puro até assentar.

**Runbook de instalação:** `docs/runbooks/edge-telemetry-collector.md` (este commit).
