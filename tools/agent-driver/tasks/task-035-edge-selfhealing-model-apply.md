---
title: "O4 self-healing + O5 edge aplica modelo (hot-swap)"
pr_title: "feat(edge): self-healing (circuit breaker GPU/supervisord) + hot-swap de modelo no edge"
commit_message: "feat(edge): supervisão de processo + circuit breaker GPU + aplicação/rollback de modelo no edge"
eval: manual-hardware
budget_minutes: 120
risk: security
requires_hardware: true
status: BLOQUEADA-HARDWARE — rodar quando o Mini PC estiver disponível. Fora da queue.txt autônoma.
---

# Tarefa 035 — Self-healing (O4) + aplicação de modelo no edge (O5) · BLOQUEADA-HARDWARE

> 🔴 Precisa do PC + GPU. Lado cloud do rollout (manifesto/pin) já vem na task-025.

## Objetivo
- **O4:** supervisão de processo (systemd/supervisord, restart de pipeline morto), circuit breaker de GPU
  (fila estoura → derruba FPS antes de travar + evento de saúde), e escalonamento (alerta com diagnóstico).
- **O5:** o edge consulta o manifesto (025), baixa o modelo novo, valida checksum, **hot-swap** sem perder
  evento; rollback automático se a saúde degradar pós-troca (staged: canário → geral).

## Depende de
- deepstream (032), edge stack (033), edge-sync-agent (034), model rollout API (025).

## Escopo (expandir ao desbloquear) / Eval (manual-hardware)
- Matar pipeline → reinicia < 30s. GPU saturada → FPS cai, sistema não trava, evento emitido.
- Publicar modelo novo (canário) → edge aplica, valida saúde, expande; degradou → rollback automático.

## Critérios de aceitação
- [ ] Self-healing nos 3 casos + hot-swap de modelo com rollback, validados no PC.

## Checkpoint
- HARDWARE. Validação humana no PC.
