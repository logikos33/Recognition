---
title: "Auditoria de operabilidade frontend↔backend + reorganização de IA/UX do painel admin"
pr_title: "docs(quality): auditoria de operabilidade frontend↔backend + proposta de IA do admin"
commit_message: "docs(quality): auditoria frontend↔backend + IA/UX do painel"
risk: low (fase 1 = auditoria read-only) → security nas correções (fase 2)
status: AUTO (fase 1 auditoria); fase 2 (correções) uma-PR-por-área, com Contrato de Operabilidade
---

# Tarefa 057 — Auditoria de operabilidade frontend↔backend + IA/UX do admin

## Por quê
Regra do FRONTEND_OPERABILITY_STANDARD.md: nenhuma feature está pronta se precisa de código pra
operar. Hoje há capacidades no backend que não têm UI (ou têm UI incompleta, sem os campos de
entrada), e o painel admin está desorganizado. Antes de construir mais, **auditar e reorganizar**.

## FASE 1 — Auditoria (read-only; produz docs; 1 PR de chore)

### 1a. Matriz de operabilidade (docs/quality/FRONTEND_BACKEND_AUDIT.md)
Para CADA endpoint de backend (varrer app/api/v1/**/routes.py) e CADA capacidade, classificar:
- ✅ **Surfaçado completo** — tem UI e todos os campos de entrada necessários.
- 🟡 **Parcial** — tem UI mas FALTAM entradas (o backend precisa de X e a tela não pede). Listar os
  campos faltantes (ex.: linha de cruzamento, classes, limiar, chave de API, nº de câmeras).
- ⚠️ **Não surfaçado (débito)** — capacidade existe no código mas NÃO tem UI. Listar.
- ❌ **UI órfã** — a tela chama endpoint que não existe / método errado (reusar CONTRATO_FRONT_BACK.md).
Para cada linha: endpoint, o que faz, entradas que o backend exige, o que a UI oferece hoje, gap, prioridade.

### 1b. Saúde dos endpoints
Smoke em staging: quais endpoints respondem como previsto, quais estão quebrados/mortos, quais têm
funcionalidade que "não executa". Listar bugs/rotas mortas.

### 1c. Débito de funcionalidade (código sem frontend)
Casos-âncora a confirmar: criação/config de modelo (linha de cruzamento p/ contagem, classes a
detectar, ROI/zona, dia/noite — o editor de cenário task-023/024 existe? está surfaçado e completo?);
seleção de modelo por câmera (task-045); retenção (task-047); notificação/flywheel; inventário
(task-052); regras/alertas. Marcar o que existe no backend mas o usuário não alcança pela tela.

### 1d. IA/UX do painel admin (docs/quality/ADMIN_IA_PROPOSAL.md)
O painel está bagunçado. Propor uma **arquitetura de informação** agrupada e fluida, ex.:
- **Operação:** câmeras/inventário, monitoramento, console de teste.
- **Modelos & Treino:** registry, treino, cenários/config de modelo, benchmark.
- **Alertas & Relatórios:** alertas, busca investigativa, relatórios.
- **Administração:** tenants, usuários, permissões, planos, feature flags, branding, integrações/segredos.
- **Suporte & Saúde:** tickets, announcements, health, workers, audit log.
Mapear cada página atual → grupo; apontar fluxos confusos e a correção de UX. Não redesenhar ainda —
propor a IA e a lista de ajustes.

## FASE 2 — Correções (após aprovar a auditoria; uma PR por área)
- Fechar os gaps por prioridade (P0 = o que bloqueia operar a RVB pela UI). CADA PR entrega o
  **Contrato de Operabilidade** da feature (entradas na UI + validação + endpoint + role).
- Reorganizar a navegação do admin conforme a IA aprovada, sem quebrar rotas existentes.
- Garantir zero regressão: todos os endpoints previstos funcionando, nada de tela que não executa.
- Segredos (chave Vast, credenciais) numa área de Integrações/Configurações cifrada — não por-uso.

## Critérios de aceite
- Matriz completa (todo endpoint classificado) + lista priorizada de gaps + proposta de IA aprovada.
- Fase 2: cada área corrigida operável 100% pela UI, com Contrato de Operabilidade, UX revisada,
  CI verde, sem regressão.

## Nota
Fase 1 é read-only e vem ANTES de qualquer construção nova (inclusive antes de finalizar 054/056).
