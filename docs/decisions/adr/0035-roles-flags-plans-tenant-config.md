# ADR-0035 — Papéis editáveis + feature flags (global + tenant) + módulos e planos por tenant

**Status:** Aceita (2026-07-07) · **Estende:** ADR-0025 (RBAC por tenant) · **Relaciona:** admin-roles,
admin-users, admin-plans, admin-tenants, admin-feature-flags, module-selection.

## Contexto (pontos F8, G9, H10, K13)

A ADR-0025 definiu o RBAC (papéis com permissões JSONB por tenant), mas o front não deixa o super admin
**definir as atividades de cada papel / editar / criar** papéis, nem dá opções no usuário além de
desativar. E o "feature flags" não tinha propósito claro. E os planos só têm usuários/módulos.

## Decisão

### 1. Papéis & permissões editáveis (estende ADR-0025)
- Super admin (todos os tenants) e tenant admin (o próprio) podem **criar/editar papéis** e **DEFINIR as
  atividades** (checklist de permissões por recurso×ação: cameras/alerts/models/training/reports/users/
  roles/settings × read/write/delete/export/admin). Papéis `is_system` não editáveis/deletáveis.
- **Usuário (F8):** ao selecionar um usuário, além de ativar/desativar → **trocar papel**, **ajustar
  permissões granulares** (permissão avulsa além do papel), reset de senha, ver atividade.

### 2. Feature flags — DOIS níveis (global + override por tenant)
- **Global:** liga/desliga uma feature nova pra TODOS (rollout/dev).
- **Override por tenant:** cada tenant pode **sobrescrever** (feature on global → off pra um tenant; off
  global → on pra um tenant). Precedência: override de tenant > global.
- Flags controlam **módulos e features**. Ex.: "Módulo Qualidade", "Training Studio", "NVR mining".

### 3. Config por tenant (K13)
- Por tenant: **quais módulos on/off**, **nome do módulo customizável** (não chumbar "EPI"), **quais
  flags habilitadas**, e as flags dos usuários daquele tenant. É onde o super admin "monta" o que o
  cliente vê.

### 4. Planos (H10)
- Cada plano define: **módulos** + **features (flags)** + **limites** (nº usuários, câmeras, dias de
  retenção, storage) + **valor de cobrança**. O plano do tenant é a **baseline**; o config por tenant
  pode ajustar via flags.

### Relação (a cadeia de habilitação)
`Plano` (baseline: módulos/features/limites) → `Config do tenant` (flags on/off + nome do módulo) →
`Papéis` (permissões dentro do que está habilitado) → `Usuário` (papel + permissões avulsas).

## Consequências
- Modelo coerente de "o que cada cliente tem" sem deploy. Risco de misconfiguration (mitigar com
  validação + defaults do plano). Precedência de flag (tenant > global) precisa ficar explícita no
  backend. Front desenha tudo; backend evolui os endpoints (flags, plan-contents).
