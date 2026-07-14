---
title: "Plug-and-play: portabilidade de rede (subnet de câmera fixo + WireGuard re-enrollment na troca de rede)"
pr_title: "feat(edge): portabilidade de rede — troca de rede sem quebrar (câmera subnet fixo + re-enroll)"
commit_message: "feat(edge): edge resiliente à troca de rede (bancada -> cliente)"
eval: manual-hardware
risk: security
requires_hardware: true
depende_de: ADR-0020
bloco: 7 (Portabilidade de rede)
---

# Task 095 — Portabilidade de rede

## Objetivo
O edge é configurado numa rede (bancada) e vai para outra (cliente) — não pode quebrar na troca.

## Escopo
- **Subnet de câmera FIXO** atrás do MikroTik (ex. 10.20.0.0/24) → IPs de câmera invariantes à WAN do cliente. (MikroTik: validar depois — parametrizável.)
- WAN do edge por DHCP; WireGuard **outbound** re-disca; re-enrollment/identidade se necessário na nova rede.
- Sem IP hard-coded; config idempotente na mudança de rede.

## Aceite
- [ ] Trocar a rede (bancada→cliente) não quebra: câmeras seguem visíveis, túnel re-conecta, sem reconfig manual.

## Checkpoint
- BLOQUEADA-HARDWARE (validar com o box + rede). MikroTik TBD.
