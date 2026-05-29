# ADR-0017 — Tenant Isolation Enforcement

## Status
Aceito — 2026-05-28

## Contexto

Durante investigação do PEND-008 (`column "status" does not exist` em polling de
`/api/v1/health/metrics`), descobriu-se que `auth.py` tem 4 funções de claim do JWT
com fallback silencioso:

- `get_tenant_schema()` → `"public"`
- `get_tenant_id()` → `"00000000-0000-0000-0000-000000000001"`
- `get_role()` → `"operator"`
- `get_modules_enabled()` → `[]`

Esses fallbacks foram introduzidos provavelmente como conveniência durante
desenvolvimento, mas em sistema multi-tenant configuram vetores de vazamento de dados.

Além disso:
1. `/api/auth/register` emitia token sem `additional_claims`, gerando tokens bugados
   para usuários novos
2. `/api/auth/login` usava `user.get("tenant_schema") or "public"`, permitindo login
   silencioso de usuário sem tenant
3. `get_schema_whitelist()` incluía `"public"` como schema válido
4. `quality/routes.py` tinha 3 lugares com f-string em `SET search_path` (SQL injection
   mitigado pelo whitelist, mas má prática)
5. `quality/routes.py:51` duplicava o fallback silencioso inline em `_require_jwt()`

## Decisão

Implementar tenant isolation com 3 camadas (defense in depth):

### Camada 1 — Claims obrigatórios
- `get_tenant_schema()`, `get_tenant_id()`, `get_role()` lançam `AuthenticationError`
  se claim ausente no JWT
- `get_modules_enabled()` mantém fallback `[]` — lista vazia é estado legítimo
- `quality/routes.py:51` usa a função centralizada em vez de fallback inline

### Camada 2 — Token issuance correto
- `/api/auth/register` não emite mais `access_token` — usuário deve fazer login
  explicitamente após criação
- `/api/auth/login` valida que `user.tenant_schema`, `user.tenant_id` e `user.role`
  existem no banco; senão retorna 401 com mensagem clara
- `"public"` removido do whitelist de schemas válidos para tenant operations

### Camada 3 — Queries com WHERE tenant_id explícito
- Top 5 queries críticas de quality auditadas e corrigidas para incluir
  `WHERE tenant_id = %s` como defense in depth
- Audit completo registrado como PEND-009

## Decisão complementar — Tenant Default Removal

Durante investigação foi descoberto que o tenant
`00000000-0000-0000-0000-000000000001` (slug=`default`, `schema_name='public'`)
é artefato legado:

- Criado em `migration 005_multi_tenant.sql` como bootstrap de dados legados
- Schema `'public'` usado como "schema do tenant default" — confusão conceitual
  entre tabelas globais e tabelas de tenant
- Conteúdo: 5 câmeras de teste (todas apontando `177.101.103.1`), 13 alerts batch
  de 2026-04-14, 1 usuário `admin@epimonitor.com` sem atividade recente

**Decisão: Opção B-clean** — desativar tenant + deletar dados + remover referências
hardcoded.

Razões:
- RVB tem tenant próprio (`rvb`, schema `rvb`) sem dados ainda em produção
- Logikos tem tenant próprio (`admin`, schema `admin`) com 2 usuários ativos
- Tenant default não tem dono ativo
- Manter o tenant força fallback `"public"` no `get_tenant_schema()` — conflita
  com ADR-0017 Camada 1

**Migration:** `042_deactivate_default_tenant.sql`

Tabelas em `public` que continham dados do tenant default (`cameras`, `alerts`,
`quality_*`, etc.): mantidas como dead tables. Limpeza tracked como PEND-010.

Bootstrap futuro: novos tenants criados via `create_tenant_schema()` sempre terão
schema próprio, nunca `'public'`. Validação adicional: `get_schema_whitelist()` exclui
`'public'` (Camada 2).

## Consequências

### Positivas
- Tokens antigos emitidos via `/register` deixam de funcionar — usuários precisam
  relogar com versão nova do código
- Endpoint que precisava de cross-tenant explicitamente (`superadmin`) passa a usar
  contexto explícito, não fallback silencioso
- Isolation testável: testes simulam token bugado e confirmam 401
- PEND-008 resolvido: `/api/v1/health/metrics` para de gerar erro 60s/req

### Negativas
- Tokens ativos serão invalidados no próximo request — usuários precisarão relogar
- Quality routes precisam de refactor mais profundo (audit completo como PEND-009)

## Verificação pós-merge

1. Tentar acessar `/api/v1/health/metrics` com token gerado antes do fix → 401
2. Tentar usar token de `/register` em qualquer endpoint autenticado → 401
3. Logs: `column "status" does not exist` deve sumir completamente
4. Login normal com `superadmin@logikos.com.br` → funciona (tem tenant_schema no banco)
5. Tenant `default` desativado: `is_active = false` + 0 cameras + 0 alerts

## Notas de migração

- Deploy automático no Railway executará migration 046 no startup
- Frontend: 401 em qualquer endpoint redireciona para login (já é comportamento padrão)
- Backup pré-execução: `/tmp/recognition-backup-20260528-221238/` (local)

## Implementação

Branch: `fix/tenant-isolation-enforcement`
