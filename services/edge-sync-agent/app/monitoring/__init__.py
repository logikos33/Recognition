"""Monitoramento local do box (/monitoring — observabilidade total do Jetson).

O requisito que decide a arquitetura: "só consome egress quando eu estiver
acessando". Logo, o histórico mora NO BOX:

  - `store.py`      — ring buffer SQLite local (10s/2h, 1min/48h, 5min/30d),
                      downsample automático, teto de tamanho e guarda de disco;
  - `sources.py`    — leitores de tegrastats/systemctl/sysfs/procfs (sem jtop/
                      AGPL: tegrastats é binário da NVIDIA, sem encargo);
  - `sampler.py`    — monta uma amostra completa (7 camadas) por tick;
  - `__main__.py`   — o daemon coletor (`python -m app.monitoring`), unit
                      systemd --user própria com teto de recurso;
  - `handlers.py`   — responde aos comandos `monitoring.*` que chegam pelo
                      canal outbound existente (command_poller — ADR-0020:
                      nada inbound, nada de porta nova);
  - `status_file.py`— artefatos de estado que outros processos (live_view,
                      heartbeat) escrevem e o coletor lê.

Sem acesso: zero byte sobe — o coletor grava local e pronto. Com acesso: só a
janela pedida viaja pelo canal de comandos.
"""
