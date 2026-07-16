"""Telemetria device-side do edge (task-100 — observabilidade MVP + baseline).

Coleta métricas do Jetson Orin via `tegrastats`, estrutura cada amostra e:
  - grava JSONL local (baseline idle/inference — estudo de dimensionamento);
  - opcionalmente mapeia para o payload `Heartbeat` e envia à API cloud
    (`POST /api/v1/edge/heartbeat`) via um sink HTTP injetado.

Rodável como serviço systemd (ver `deploy/edge-telemetry-collector.service`),
resolvendo o caveat do coletor nohup que não sobrevive a reboot.
"""
from .tegrastats_parser import TegrastatsSample, parse_tegrastats_line

__all__ = ["TegrastatsSample", "parse_tegrastats_line"]
