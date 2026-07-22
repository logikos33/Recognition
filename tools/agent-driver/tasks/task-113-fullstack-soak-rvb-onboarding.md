---
title: "FINAL PRÉ-CUTOVER: soak test full-stack (Postgres+Redis+API+3 módulos no box) + otimização + embarque RVB (local+web)"
pr_title: "feat(edge): soak full-stack co-residente + otimizações de memória + embarque RVB dual-mode"
commit_message: "feat(edge): full-stack soak no Orin + hardening de memória + vínculo RVB local/web"
eval: manual-hardware
risk: security
requires_hardware: true
prioridade: MÁXIMA (último teste antes do cutover)
depende_de: task-111 (3 módulos), task-108-110/112 (esqueletos), ADR-0046 (dual), ADR-0048
---

# Task 113 — Soak full-stack + otimização + embarque RVB (o último teste antes de tombar)

## Objetivo
Provar que o box NÃO TRAVA com a stack COMPLETA co-residente (Redis local + Postgres local + API + edge-sync +
3 módulos de inferência + túnel + dashboard) rodando por HORAS; aplicar as otimizações de memória/performance; e
EMBARCAR a RVB (tenant, câmeras, modelos, dual-mode local+web). Medo explícito do Vitor: travamento pós-cutover.

## Fundamento (pesquisa)
Jetson = MEMÓRIA UNIFICADA: CPU e GPU dividem os 16GB → RAM de Postgres/Redis compete DIRETO com a inferência.
Mitigações padrão: swap em NVMe (não zram-only), swappiness baixo, MemoryMax (systemd) por serviço, Redis
maxmemory+policy, Postgres shared_buffers pequeno, oom_score_adj protegendo o pipeline. Fontes no prompt.

## Escopo
1. **Hardening de memória (antes do soak):** budget explícito por serviço (systemd MemoryMax): Postgres, Redis,
   API, edge-sync, coletor. Redis `maxmemory` + `allkeys-lru`(ou policy adequada); Postgres `shared_buffers`
   dimensionado pra edge; swap NVMe + `vm.swappiness` baixo; `oom_score_adj` alto p/ serviços auxiliares e
   BAIXO p/ DeepStream (pipeline morre por último). jetson_clocks + fan `cool` (sudo, gate Vitor, se disponível).
2. **Otimizações adicionais (bench-based, liberdade):** o que a pesquisa indicar com ganho real (EMC, NVMM pools,
   batch, etc.) — aplicar e MEDIR o ganho de cada uma.
3. **SOAK full-stack (o teste central):** stack COMPLETA co-residente + os 3 módulos na config de produção,
   rodando **≥4h contínuas** (ideal overnight): medir RAM/pressão/PSI, GPU, temps, potência, swap-in/out, latência
   da API, filas, drops. Injetar carga realística (eventos, evidências, queries no dashboard). **Chaos leve:**
   matar/reiniciar serviços (systemd deve recuperar), reboot completo → tudo volta sozinho.
4. **Embarque RVB (vínculo sistema↔edge):** tenant/site RVB, 28 câmeras cadastradas (grupos/módulos/modelos por
   câmera via active_module+model_<módulo>_id), deployment_mode dual; **rodar LOCAL (LAN) e WEB** (nuvem via túnel)
   — operador acessa dos dois; enrollment do device; sync funcionando.
5. **Critério de aprovação (gate de cutover):** ≥4h sem OOM/travamento/throttle; RAM estável (sem crescimento
   monotônico=leak); todos os módulos na cadência-alvo; API local E web respondendo; recuperação automática provada.

## Aceite
- [ ] Relatório do soak (horas, curvas de RAM/PSI/GPU/temp, incidentes zero ou explicados) + veredito GO/NO-GO de cutover.
- [ ] Budgets de memória e otimizações documentados (config de produção final). RVB embarcada local+web.

## Checkpoint
- BLOQUEADA-HARDWARE. Execução AUTÔNOMA (Vitor na estrada) — não parar em gates evitáveis; status ao final.
