# Task 073 — [SEC] `PATCH /api/modules/<code>/classes/<id>` sem tenant_id/role (achado #6)

**Status**: CONCLUÍDO (2026-07-12) — ver seção "Execução" ao final.
**Risk**: security (P0 — cross-tenant)
**Branch**: fix/sec-modules-classes-tenant-isolation (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #6 · **Relaciona**: ADR-0017, ADR-0025, C-01.

## Problema (produção)
`PATCH /api/modules/<module_code>/classes/<class_id>` (ativar/desativar classe) **não filtra `tenant_id`
nem checa role**. Qualquer usuário JWT de **qualquer tenant** pode ativar/desativar qualquer classe
globalmente.

## Fix
- Filtrar por `get_tenant_id()` no repository/service (a classe tem que pertencer ao tenant).
- Exigir role com permissão de escrita (`models`/`settings` write, ADR-0025).
- Classe de outro tenant → 404 (padrão cross-tenant, C-01), não 403 vazando existência.

## Teste (falha-antes/passa-depois)
- Tenant A tenta togglar classe do tenant B → 404 (antes: 200). Usuário sem permissão → 403.

## Aceite
- Query com `tenant_id`; 404 cross-tenant; role checada; teste prova; ruff+pytest verde; PR develop; STOP.

## Execução — 2026-07-12

### Descoberta de schema (leitura real, não inferência)

`module_classes` (migration `009_module_classes.sql`) é um **catálogo global** — sem coluna
`tenant_id` — compartilhado por todos os tenants que têm um dado `module_code` (`epi`/`fueling`)
habilitado. Não confundir com `yolo_classes` (migration `093_classes_tenant_module.sql`), que É
tenant-scoped mas serve a feature diferente (`/api/classes`, classes customizadas de treino por
tenant/WS-A1). O achado #6 é sobre o catálogo global, não sobre `yolo_classes`.

Dado que `module_classes` não tem `tenant_id`, o "filtro por tenant_id" exigido pelo spec foi
implementado da única forma consistente com o schema real, sem migration nova (mudança de schema
fora do escopo desta task de segurança):

1. **`tenant_has_module(tenant_id, module_code)`** (já existente em `ModuleService`, mesma lógica
   usada por `GET .../stats`) — o tenant requisitante precisa ter o módulo habilitado em
   `tenant_modules` antes de poder alterar qualquer classe daquele módulo.
2. **`module_repository.toggle_class_active(module_code, class_id, is_active)`** — o `UPDATE` agora
   filtra por `WHERE id = %s AND module_code = %s` (antes: só `id`). Isso impede que um `class_id`
   de outro `module_code` seja alterado através da URL de um módulo diferente.
3. Qualquer uma das duas falhas → `NotFoundError` (404) — nunca 403, para não vazar a existência de
   classes de módulos que o tenant não acessa (C-01).
4. Novo gate de permissão `modules:write` (`app/core/permissions.py`, `default_roles=[admin,
   superadmin]`, `enforced=True`) checado via `has_permission()` (`app/core/tenant.py`, padrão WS7 —
   mesmo idioma de `notifications:manage`/`devices:manage`) antes de qualquer leitura/escrita.

### Arquivos alterados

- `services/api/app/api/v1/modules/routes.py` — `toggle_module_class`: gate `has_permission("modules:write")`
  (403 se ausente), `get_tenant_id()` passado ao service, `except NotFoundError: raise` (antes o
  `except Exception` genérico mascarava o `NotFoundError` do service em 500 — bug latente corrigido
  como parte necessária do fix, já que sem isso o 404 do teste nunca se manifestava).
- `services/api/app/domain/services/module_service.py` — `toggle_class(tenant_id, module_code,
  class_id, is_active)`: checa `tenant_has_module` antes de tocar o repository.
- `services/api/app/infrastructure/database/repositories/module_repository.py` —
  `toggle_class_active(module_code, class_id, is_active)`: `UPDATE` com `WHERE id=%s AND
  module_code=%s`.
- `services/api/app/core/permissions.py` — novo grupo "Módulos", chave `modules:write`.
- Testes atualizados/criados: `tests/unit/api/test_modules_routes.py` (novo — cobre 403 sem
  permissão, 404 cross-tenant módulo não habilitado, 404 class_id de outro módulo, 404 módulo
  desabilitado, 200 happy path admin/superadmin), `tests/unit/domain/test_module_service.py`,
  `tests/unit/infrastructure/test_module_repository.py`, `tests/unit/core/test_permissions_registry.py`
  (paridade `modules:write` == `{admin, superadmin}`).

### Falha-antes/passa-depois (evidência)

Reproduzido isoladamente: com `git stash` das mudanças de código-fonte (mantendo só um teste de
prova em cima do código original), uma requisição com role `operator` e `tenant_id` arbitrário
(sem nenhuma relação com o módulo/classe alvo) para
`PATCH /api/modules/fueling/classes/fueling-class-de-outro-tenant` retornava **200** — confirmando
a vulnerabilidade. Após restaurar o fix, o mesmo cenário (role sem permissão OU tenant sem o módulo
habilitado OU class_id de outro módulo) retorna 403/404 conforme o caso — ver
`tests/unit/api/test_modules_routes.py::TestToggleModuleClassPermission` e
`::TestToggleModuleClassTenantIsolation`.

### Validação

- `ruff check services/api/` — sem erros.
- `pytest services/api/tests/ -q --cov=app --cov-fail-under=60` — 3438 passed, 47 skipped
  (baseline pré-existente), cobertura 66.71%.
- Skill `security-review` executada sobre o diff antes do PR (achados tratados — ver descrição do PR).

### Nota de escopo (não corrigido aqui)

`module_classes` ser um catálogo global compartilhado entre tenants (em vez de ter overrides
por tenant) é uma característica de design pré-existente, não uma regressão desta task — ativar
uma classe do módulo `epi` afeta todos os tenants que usam `epi`. Adicionar `tenant_id` a
`module_classes` (permitindo catálogos por tenant) seria uma migration + mudança de lógica de
aplicação maior, fora do escopo de um fix de segurança pontual (violaria a regra de não misturar
migration + lógica no mesmo commit). Registrado aqui para triagem futura caso o produto precise de
customização de classes por tenant além do catálogo global atual.
