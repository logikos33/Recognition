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

## Atualização (task-094, 2026-07-15)
Investigação C-04 confirmou que o caminho câmera→nuvem, a criação de câmera e o gate de evidência (task-092)
já operam cloud-only por padrão, sem código novo. O trade-off de isolamento de câmera citado acima (lockout)
foi formalizado em **ADR-0051**: cloud-only tem dois sub-níveis — com gateway de site (MikroTik, mínimo
recomendado) e sem gateway (não recomendado em produção). Ver ADR-0051 para o detalhamento e para a decisão
sobre `public.tenants.deployment_mode` (coluna existente desde a migration 067, intencionalmente não lida —
fonte de verdade é por site, `edge_sites.deployment_mode`).
