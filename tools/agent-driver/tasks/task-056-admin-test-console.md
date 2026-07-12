---
title: "Console de teste de operação no painel admin (E2E pela plataforma, sem terminal)"
pr_title: "feat(admin): console de teste E2E — harness, seleção de modelo, métricas ao vivo"
commit_message: "feat(admin): console de teste de operação no painel admin"
risk: security
status: AUTO (cloud)
---

# Tarefa 056 — Console de teste de operação (painel admin)

## Por quê
Filosofia de SaaS auto-administrável (AUTOADMIN_STUDY.md) + regra do FRONTEND_OPERABILITY_STANDARD.md:
a operação de teste ponta a ponta é feita NA plataforma, não no terminal. Valida o E2E na nuvem antes
da RVB e serve depois como tela de "operação de teste" pra qualquer cliente novo antes do go-live.

## Contrato de Operabilidade (entradas que a UI PRECISA ter — obrigatório)
Sem estes campos na tela, a feature NÃO está pronta (não pode depender de script):
- **Chave da Vast / segredos:** NÃO digitar a cada teste — ficam em **Configurações → Integrações**
  (cifradas); o console apenas usa. Se ausente, mostrar aviso + link pra configurar.
- **Nº de câmeras simuladas:** seletor (ex.: 1–28) na tela.
- **Seleção de modelo:** dropdown do registry (pré-treinado / EPI YOLOX / RF-DETR).
- **Config do modelo/cenário quando aplicável:** contagem → **desenhar a linha de cruzamento**;
  EPI/detecção → **escolher classes** + **zona/ROI** + limiar de confiança. Reusar o editor de
  cenário (task-023/024) NO fluxo — nada de JSON na mão.
- **Ações:** start/stop com estados (loading/erro/sucesso) e **feedback ao vivo**.
- **Role:** admin/superadmin; tudo sobre tenant de TESTE isolado.

## Escopo
### Frontend (apps/frontend/src/modules/admin, ex.: AdminTestConsolePage)
- Todos os campos do Contrato acima. Acompanhar AO VIVO: câmeras simuladas, detecções/alerts em tempo
  real, latência, throughput (inf/s), uso de conexão/VRAM quando disponível; destacar o ponto de
  degradação ao escalar. Link pra evidência no R2. Usar `api.ts` (sem fetch raw).

### Backend (services/api/app/api/v1/admin)
- Endpoints role-gated: start/stop do harness (task-027), status/métricas da operação, seleção de
  modelo (reusar model registry / task-045 rollout / task-052 inventário). Filtrar por tenant de
  teste; SQL parametrizado; nada cross-tenant. Ler a chave da Vast do store de integrações cifrado.

## Critérios de aceite
- Operador dispara e acompanha o teste E2E inteiro PELA UI (câmeras → modelo → config → start →
  métricas ao vivo), sem terminal. Contrato de Operabilidade 100% atendido.
- Tenant de teste isolado; role-gated; isolamento testado.
- Testes: start/stop, seleção/config de modelo, métricas, isolamento por tenant.

## Risco
security — controla ingest/modelo + segredos + isolamento por tenant. Review C2.
