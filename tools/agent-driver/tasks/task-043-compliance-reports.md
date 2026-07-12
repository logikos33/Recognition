---
title: "Relatórios de compliance agendados (PDF) — melhoria C"
pr_title: "feat(reports): relatório de compliance (PDF) on-demand + geração agendada pra R2"
commit_message: "feat(reports): agregação de conformidade EPI/violações + PDF + agendamento, tenant-scoped"
eval: default
budget_minutes: 90
risk: security
---

# Tarefa 043 — Relatórios de compliance agendados · melhoria C

## Objetivo
O cliente compra GESTÃO, não detecção crua. Gerar **relatório de compliance** (PDF) a partir dos dados que já
existem: % de conformidade de EPI, violações por turno/zona, tendência e top reincidências. On-demand + geração
agendada gravando no R2. **Read-only + R2 + scheduler — sem hardware, sem migration** (v1 sem tabela nova: grava
no R2 com chave determinística `tenant/<id>/reports/<periodo>.pdf`). Ver `docs/architecture/ARQUITETURA_E_MELHORIAS.md` (C).

## Contexto (LER antes — C-04; C-01)
- repos de alertas/detecções existentes (agregação); dashboard/export atual como referência de números.
- infraestrutura R2 (`R2Storage`/boto3); scheduler-service (geração periódica). get_tenant_id (C-01).

## Comportamento
- `GET /api/v1/reports/compliance?period=<dia|semana>&from=&to=` (JWT, tenant de get_tenant_id):
  agrega conformidade/violações por turno/zona/câmera no período; retorna sumário + URL do PDF.
- Geração do **PDF** (usar a skill/lib de PDF do projeto) com os KPIs + tabela de reincidências; grava no R2.
- Job agendado (diário) que gera e arquiva no R2 por tenant. (Entrega por e-mail/WhatsApp = melhoria A/044, não aqui.)
- TUDO tenant-scoped: jamais agregar dado de outro tenant (C-01); cross-tenant → vazio/404 coerente.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/reports/ (endpoint + serviço de agregação + geração PDF)
- integração R2 existente; tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério (DB real, padrão PR #25)
- seed de alertas/detecções de 2 tenants → relatório do tenant A não inclui nada do B (C-01).
- agregação correta (contagens/percentual) num período conhecido; PDF gerado e enviado ao R2 (mock do storage ok).
- sem JWT → 401. ruff + pytest + tsc verdes.

## Critérios de aceitação
- [ ] Agregação de compliance tenant-scoped + PDF no R2 + job agendado; testes verdes. PR para develop.

## NEEDS CLARIFICATION
- Se a definição de "turno" não existir no schema, parametrizar (ex: janelas horárias por config) e reportar.

## Checkpoint
- Só PR (humano revisa — exporta dado agregado, risk security). Sem produção. Sem migration.
