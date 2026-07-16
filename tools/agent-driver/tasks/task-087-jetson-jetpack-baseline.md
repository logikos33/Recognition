---
title: "Edge Jetson: baseline JetPack + stack plug-and-play (ARM) — reescreve task-033 x86→ARM — HARDWARE"
pr_title: "feat(edge): stack Jetson (JetPack/DeepStream/TensorRT/MediaMTX) plug-and-play ARM"
commit_message: "feat(edge): baseline Jetson Orin (JetPack + install.sh ARM)"
eval: manual-hardware
risk: security
requires_hardware: true
supersede: task-033 (OBSOLETA — mini-PC descartado)
depende_de: ADR-0040
bloco: 4 (Edge Jetson + VST)
---

# Task 087 — Baseline JetPack (reescreve 033 para ARM)

## Objetivo
Provisionar o Jetson Orin NX 16GB: JetPack/Jetson Linux + DeepStream + TensorRT + MediaMTX + Redis local +
edge-sync-agent, com `install.sh` **ARM/JetPack** (a task-033 pressupunha um mini-PC descartado — não serve).

## Escopo
- install.sh ARM: nvidia stack (JetPack), DeepStream, TensorRT (build de engine on-device), MediaMTX, Redis, UFW.
- Rede: WireGuard outbound (ADR-0020). MikroTik TBD (task-095).

## Aceite
- [ ] Box liga e sobe o stack; engine TensorRT compila no device; healthcheck OK.

## Checkpoint
- BLOQUEADA-HARDWARE (box amanhã). Substitui 033.

## Achados de sessão (2026-07-16) — pendências resolvidas

- **SSH por chave habilitado** — `~/.ssh/authorized_keys` do `pandora` recebeu a chave pública da estação de
  trabalho; acesso autônomo (sem senha) confirmado via `ssh pandora@100.93.126.76` (Tailscale). A sessão
  anterior só tinha acesso por senha.
- **Timezone/NTP já corretos** — `timedatectl status` confirma `America/Sao_Paulo`, `System clock
  synchronized: yes`, `NTP service: active`. O TODO desta task sobre "relógio veio errado/UTC, rodar
  `timedatectl set-timezone`" **não se aplica mais** — já foi corrigido em algum momento entre as sessões
  (não determinado quando/por quem).
- **`sudo` continua exigindo senha** (não há sudoers passwordless configurado) — ações que precisam de root
  (ex.: `apt install`) exigem alguém fisicamente/interativamente digitando a senha num terminal; não é algo
  que a automação deve tentar contornar.
