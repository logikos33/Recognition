---
title: "Liveness por câmera + alerta de falha silenciosa (contenção R7)"
pr_title: "feat(edge): alerta de liveness por câmera (não só site offline)"
commit_message: "feat(edge): regra de liveness por câmera a partir do heartbeat + alerta de câmera parada"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 040 — Liveness por câmera · contenção R7 (falha silenciosa)

## Objetivo
Pesquisa: câmera para de detectar sem ninguém avisar ("worked, then died silently"). Conter com o heartbeat que
já temos: derivar **liveness por câmera** e **alertar quando UMA câmera fica stale** (não só quando o site cai).
Cloud, tabelas existentes, sem hardware. Ver CONTENCAO_RISCOS_ESCALA.md (R7).

## Contexto (LER antes — C-04; C-01)
- app/api/v1/edge/* (heartbeat ingest + health). O heartbeat já carrega cameras_online/total (O1).
- alert_rules (engine de alerta) + responses success/error; get_tenant_id (C-01).

## Comportamento
- Regra: por site, se `cameras_online < cameras_total` por > N min (configurável) → evento/alerta de saúde
  identificando o gap. Se o payload trouxer status por câmera, alertar a câmera específica; senão, alertar o gap
  agregado e registrar [NEEDS CLARIFICATION] de que o detalhe por câmera precisa enriquecer o heartbeat (edge/034).
- Recuperação (cameras_online == total) limpa o alerta. Expor o estado no painel Sites & Saúde (O1). Tenant-scoped.

## Arquivos
- app/api/v1/edge/ (regra + alerta), app/domain/services/ (lógica), tests novos.
- (front opcional) apps/frontend painel Sites & Saúde.

## Eval (default) — testes SÃO o critério (DB real, padrão PR #25)
- heartbeat com cameras_online<total por > N min → alerta emitido; recuperação limpa o alerta.
- isolamento tenant (C-01): alerta só no tenant dono; sem JWT → 401.
- ruff + pytest verdes.

## Critérios de aceitação
- [ ] Liveness por câmera/gap a partir do heartbeat + alerta; tenant-scoped; testes verdes. PR para develop.

## Checkpoint
- Só PR (humano revisa — caminho de alerta/ingest, risk security). Sem produção. Sem migration.
