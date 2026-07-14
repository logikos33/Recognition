# Task 073 — [SEC] `PATCH /api/modules/<code>/classes/<id>` sem tenant_id/role (achado #6)

**Status**: PENDING · **Risk**: security (P0 — cross-tenant)
**Branch**: fix/sec-modules-classes-tenant-isolation (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #6 · **Relaciona**: ADR-0017, C-01.

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
