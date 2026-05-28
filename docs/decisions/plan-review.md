# Revisão Crítica do EDGE_DEPLOYMENT_PLAN.md

**Data:** 2026-05-27
**Branch:** staging
**Baseado em:** diagnóstico real do repositório (41 migrations, código lido, estrutura verificada)

---

## Mudanças Obrigatórias (plano factualmente incorreto)

### MO-01: Numeração de migrations
**Problema:** Plano descreve migrations 013–016 como novas. Na realidade existem 41 migrations (001–041). As migrations 013–041 já têm outros conteúdos completamente diferentes.
**Correção aplicada:** Renomeadas para `042_edge_sites.sql`, `043_device_tokens.sql`, `044_site_id_columns.sql`, `045_deployment_mode.sql`. EDGE_DEPLOYMENT_PLAN.md atualizado.

### MO-02: painel-adm/ é repositório git aninhado
**Problema:** Plano assume `git mv painel-adm/auth-service/ services/auth/` etc. diretamente. `painel-adm/` tem `.git` próprio — `git mv` não funciona.
**Correção:** Fase 0 começa com Pre-4: backup + `rm -rf painel-adm/.git` + `git add painel-adm/`. Só então os `git mv`. Ver ADR-0011.

### MO-03: Arquivos inexistentes referenciados na Fase 0
**Problema:** Plano diz "Mover `Arquitetura_Final_Recognition_RVB.md` e `Arquitetura_Inicial_Netbar.md` para `docs/architecture/`". Esses arquivos não existem no repositório.
**Correção:** Esses 2 itens removidos da Fase 0. Em vez disso: mover `docs/EDGE_AGENT_ARCHITECTURE.md` → `docs/architecture/EDGE_AGENT_ARCHITECTURE.md`.

### MO-04: painel-adm/ contém mais que 6 serviços
**Problema:** Plano lista 6 serviços para mover. Na realidade `painel-adm/` tem também: `backend/`, `frontend/`, `landing-page/`, `migrations/`, `pre-annotation-service/`, `agent/`. Destino desconhecido.
**Correção:** Pre-4 investigation task antes da Fase 0. Decisão de Vitor por diretório (ARCHIVE/DELETE/MERGE). Fase 0 só executa após decisão.

### MO-05: Bug pré-existente em quality_inference.py
**Problema:** `quality_inference.py:90` referencia tabela inexistente `training_models`.
**Correção:** Pre-1 fix antes de qualquer outra tarefa. Branch `feature/preflight-fixes`, commit: `fix(quality): corrigir referência tabela training_models → models`.

### MO-06: CI/CD criado do zero (não "configurado")
**Problema:** Plano diz "Configurar `.github/workflows/ci.yml`" sugerindo que existe algo. Não existe `.github/` nenhum.
**Correção:** Entendimento correto: criar do zero. Baixo impacto, mas expectativa ajustada.

### MO-07: CLAUDE.md desatualizado
**Problema:** CLAUDE.md na raiz do projeto diz "Última: `012_camera_fields.sql`". A última real é `041_update_fueling_classes.sql`.
**Correção:** Atualizar CLAUDE.md na Fase 0 (seção de Migrations Protocol).

---

## Mudanças Sugeridas (melhorias ao plano)

### MS-01: auth-service marcado como DEPRECATED desde a Fase 0
**Contexto:** auth-service em `painel-adm/` não está integrado ao frontend. Auth real é em `services/api/app/api/v1/auth/`. O plano o move para `services/auth/` como se fosse equivalente.
**Sugestão aplicada:** Na Fase 0, mover para `services/auth/` + criar `SDD.md` marcando como `DEPRECATED — auth canônico em services/api`. Não adicionar ao `docker-compose.dev.yml`.

### MS-02: Fase -1 / "pre-flight" com 4 tasks antes da Fase 0
**Sugestão aplicada:** Adicionada pré-fase explícita:
- Pre-1: Fix `quality_inference.py:90`
- Pre-2: (reservado)
- Pre-3: chat/assistant — sem ação (OQ-001 resolvida)
- Pre-4: Investigação de `painel-adm/` internals

### MS-03: Fase S1 deve incluir fixes de tenant_id gaps documentados
**Contexto:** CLAUDE.md lista 2 queries sem `tenant_id` em `frame_repository.py` como débito técnico P3. Fase S1 auditoria deve incluí-las explicitamente.
**Sugestão:** Adicionar ao critério de aceitação da Fase S1: "script de auditoria cobre `frame_repository.py:get_annotated_by_video` e `count_validated`".

### MS-04: Quality module tasks EDGE — plano de transição explícito
**Contexto:** 6 Celery tasks EDGE estão rodando no cloud hoje para cliente em produção (Quality module ativo).
**Sugestão aplicada:** Shadow mode + cutover por câmera (ADR-0013). Fase 6.5 adicionada ao plano. Migrations 046–047 adicionadas à Fase 1.

### MS-05: docker-compose.dev.yml sem DeepStream direto
**Contexto:** DeepStream requer NVIDIA GPU + container específico.
**Sugestão:** docker-compose.dev.yml usa profile `--profile gpu` separado ou mock para inference. Service `inference` em modo dev usa `INFERENCE_ENGINE=ultralytics` por padrão.

---

## Itens do Plano que Não Fazem Mais Sentido

### IO-01: "scheduler-service adicionar railway.toml na Fase 3"
**Situação:** Confirmed que não tem railway.toml. O serviço parece não estar deployado no Railway atualmente. Pode não ser urgente adicionar.
**Recomendação:** Manter na Fase 3 mas com contexto: verificar se scheduler-service está rodando em Railway antes de criar railway.toml.

### IO-02: "Celery tasks de inferência são removidas do monolito" — timing incerto
**Situação:** O plano implica que na Fase 3 as tasks saem do monolito. Com shadow mode (ADR-0013), isso só acontece após Fase 6.5 + 30 dias estável — fora do escopo deste plano.
**Recomendação:** Fase 3 refatora os serviços para suportar edge, mas NÃO remove tasks do monolito. Remoção é pós-RVB-go-live.

---

## Itens que Precisam de Decisão Antes de Executar

| ID | Questão | Status |
|----|---------|--------|
| OQ-001 | Chat/assistant | ✅ Mantida experimental |
| OQ-002 | painel-adm/ internals | ⏳ Aguarda Pre-4 investigation |
| OQ-003 | Tasks EDGE durante migração | ✅ Shadow mode aprovado |
| OQ-004 | `models` canônica | ✅ Confirmado |
| OQ-005 | Branch base | ✅ `develop` from `staging` |
