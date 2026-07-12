---
title: "Edge stack plug-and-play + MikroTik provisioning (Fase 6 / O2)"
pr_title: "feat(edge): docker-compose edge + install.sh + nvidia/tailscale/cloudflared/UFW + MikroTik"
commit_message: "feat(edge): stack edge plug-and-play (install.sh) + provisionamento MikroTik WireGuard"
eval: manual-hardware
budget_minutes: 120
risk: security
requires_hardware: true
status: BLOQUEADA-HARDWARE — rodar quando o Mini PC estiver disponível. Fora da queue.txt autônoma.
---

# Tarefa 033 — Edge stack plug-and-play (Fase 6) + MikroTik (O2) · BLOQUEADA-HARDWARE

> 🔴 Precisa do Mini PC + MikroTik. Scripts podem ser escritos antes, mas só validam no equipamento.

## Objetivo
Tudo que faz o PC chegar na RVB e rodar em ~30 min: docker-compose edge, `install.sh` idempotente, setup
NVIDIA/driver, Tailscale/Cloudflared, firewall UFW, e o **provisionamento do MikroTik** (WireGuard hub-and-spoke
pro cloud via API RouterOS, conforme ADR-0020 e a tabela site_gateways da task-031).

## Depende de
- Mini PC + MikroTik; site_gateways (031); deepstream (032); edge-sync-agent (034).

## Escopo (expandir ao desbloquear)
- docker-compose.edge.yml (deepstream + edge-sync-agent + redis/mqtt local + cloudflared), restart policies.
- install.sh idempotente (driver NVIDIA, container toolkit, Tailscale, UFW, cloudflared) — re-rodável.
- Provisionar MikroTik: gerar par WG no cloud → push via RouterOS API → MikroTik disca outbound pro hub → anuncia LAN.
- Câmera nunca exposta; firewall na borda só libera a overlay → RTSP.

## Eval (manual-hardware)
- No PC: install.sh do zero → stack sobe; MikroTik conecta na overlay; cloud alcança o Mini PC e as câmeras.

## Critérios de aceitação
- [ ] PC + MikroTik provisionados; overlay segura; stack sobe idempotente; validado no equipamento.

## Checkpoint
- HARDWARE. Validação humana no PC. Provisionamento toca rede do cliente → cuidado redobrado.
