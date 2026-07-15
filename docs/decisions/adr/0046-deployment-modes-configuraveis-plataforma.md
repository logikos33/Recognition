# ADR-0046 — Modos de deployment configuráveis na plataforma (edge / dual / cloud-only)

**Status:** Aceito · **Data:** 2026-07-14 · **Autores:** Vitor Emanuel (Logikos)
**Estende:** ADR-0007 (deployment modes) · **Relaciona:** ADR-0045, task-036 (dual-mode)

## Contexto
Nem todo cliente terá edge. O modo de operação não pode ser premissa hard-coded: precisa ser **ajustável na
plataforma, por tenant/site, sem código**. Requisitos: dual-mode (roda local se a internet cair, acessível
remoto) e um fluxo **cloud-only** como feature para clientes sem edge.

## Decisão
- `DEPLOYMENT_MODE` (edge | dual | cloud_only) vira **configuração de tenant/site editável na UI** (não env).
- **Dual-mode** (task-036): edge serve a LAN local e sincroniza com a nuvem; queda de internet não derruba o site.
- **Cloud-only** = feature para cliente sem edge (câmera→nuvem). Tratado como feature explícita (task-094),
  ciente de que o design de isolamento de câmera (lockout) pode exigir um edge mínimo — a decidir por cliente.

## Consequências
- UI de configuração de modo por site (task-093) + fluxo cloud-only (task-094).
- Frontend precisa resolver a origem (LAN edge vs nuvem) por modo.
