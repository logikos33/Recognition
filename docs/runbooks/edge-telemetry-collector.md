# Runbook — Coletor de telemetria do edge (task-100)

Coletor device-side que amostra `tegrastats` no Jetson Orin, grava um dataset
JSONL local (baseline idle/inference para dimensionamento) e, opcionalmente,
envia heartbeats à API de observabilidade (`POST /api/v1/edge/heartbeat`).

Substitui o coletor ad-hoc `tegrastats … --logfile … (nohup)` da sessão de
bancada, que **não sobrevivia a reboot**. Aqui roda como serviço systemd.

**Código:** `services/edge-sync-agent/app/telemetry/` (parser, coletor, entrypoint).
**Testes (offline):** `services/edge-sync-agent/tests/test_tegrastats_parser.py`,
`test_telemetry_collector.py`.

---

## Instalação no box (a fazer quando o SSH estiver liberado)

> Nenhum passo abaixo mexe em rede/firewall/boot — é seguro para execução
> autônoma. A criação do serviço systemd é reversível (`disable`/`rm`).

1. Levar o `edge-sync-agent` para o box (ex.: `/opt/recognition/edge-sync-agent`).
2. Config:
   ```bash
   sudo mkdir -p /etc/recognition
   sudo cp deploy/edge-telemetry.env.example /etc/recognition/edge-telemetry.env
   sudo nano /etc/recognition/edge-telemetry.env   # ajustar EDGE_DEVICE_ID etc.
   ```
3. Serviço:
   ```bash
   sudo cp deploy/edge-telemetry-collector.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now edge-telemetry-collector
   ```
4. Verificar (read-only):
   ```bash
   systemctl status edge-telemetry-collector
   journalctl -u edge-telemetry-collector -f
   ls -la /home/pandora/edge-telemetry/     # datasets JSONL
   ```

## Captura de baseline (o estudo de dimensionamento da task-100)

1. **Idle** — com o box ocioso, `EDGE_TELEMETRY_PHASE=idle`, deixar rodando
   (uma noite). Gera `idle_<ts>.jsonl`.
2. **Inference** — ao subir o pipeline DeepStream (task-088), trocar para
   `EDGE_TELEMETRY_PHASE=inference` e `systemctl restart`. Gera
   `inference_<ts>.jsonl` comparável.
3. Cada linha do JSONL: `ts`, `phase`, `cpu_pct`, `gpu_pct`, `gpu_temp_c`,
   `cpu_temp_c`, `ram_*`, `power_in_mw`, etc. Comparar idle vs inference dá o
   headroom por carga (base do dimensionamento).

## Sink de heartbeat (dashboard de observabilidade na nuvem)

- **Desligado por padrão** (só JSONL local). A parte cloud (painéis, schema
  `gpu_temp_c`/`decode_pct`, migrations 088/089) **já está no develop**.
- Para ligar: `EDGE_API_URL` + `EDGE_DEVICE_BEARER` no env. **Requer o device
  enrolado** (token RS256 — fluxo de provisionamento, task-097). Sem enrollment,
  mantenha desligado; o baseline local não depende disso.

## Notas / limites

- Campos de pipeline (`inference_fps`, câmeras, `decode_*`) ficam ausentes até o
  DeepStream (task-088) fornecê-los — o coletor só preenche o que o `tegrastats`
  expõe (CPU/GPU/RAM/temp/potência).
- NIC do box é `enP8p1s0` (não `eth0`) — o coletor não depende de NIC, mas
  scripts de rede vizinhos sim (ver task-095).
