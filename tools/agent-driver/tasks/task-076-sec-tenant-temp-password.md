# Task 076 — [SEC] senha temporária de tenant previsível (achado #4)

**Status**: CONCLUÍDA (2026-07-12) · **Risk**: security (P0 — credencial previsível)
**Branch**: fix/sec-tenant-temp-password-random (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #4 · **Relaciona**: ADR-0025.

## Problema (produção)
`POST /api/v1/admin/tenants` gera a senha do admin do tenant como
`f'EpiMonitor@{slug[:4].upper()}2024!'` — **previsível** (deriva do slug) + ano hardcoded `2024` num
projeto em 2026. Qualquer um que saiba o slug adivinha a senha inicial.

## Fix
- Gerar senha **aleatória forte** (`secrets.token_urlsafe`, ≥16 chars, com política mínima) por tenant.
- Devolver a senha **uma única vez** na resposta de criação (já é o fluxo) e **forçar troca no 1º login**.
- Não logar a senha; garantir hash forte no armazenamento (confirmar que já usa hash, não plaintext).

## Teste (falha-antes/passa-depois)
- Duas criações → senhas diferentes e não derivadas do slug; flag "must_change_password" setada.

## Aceite
- Senha aleatória + troca no 1º login; teste prova aleatoriedade; ruff+pytest verde; PR develop; STOP.

## Execução — 2026-07-12

- **Diagnóstico**: `services/api/app/api/v1/admin/routes.py` já tinha o padrão CORRETO em outro
  handler do mesmo arquivo — `POST /api/v1/admin/users` (linha ~841) já usava
  `secrets.token_urlsafe(12)` + `hash_password()` (bcrypt) para senha temporária. Só o handler de
  criação de TENANT (`POST /api/v1/admin/tenants`, linha ~331) ainda usava o padrão previsível
  `f"EpiMonitor@{slug[:4].upper()}2024!"`. Fix: alinhar `create_tenant()` ao padrão já estabelecido
  em `create_user()`, em vez de inventar um novo mecanismo.
- **`secrets.token_urlsafe(12)`** produz string de 16 caracteres (96 bits de entropia) — confirmado
  empiricamente (`len(secrets.token_urlsafe(12)) == 16`), satisfaz o requisito de ≥16 chars sem
  precisar aumentar o parâmetro além do já usado em `create_user`.
- **Mecanismo de troca obrigatória: reusado, não criado**. A coluna `users.force_password_reset`
  (BOOLEAN, migration `029_admin_panel.sql`) já existe e já é usada em dois lugares: no INSERT de
  `create_user()` (seta `true` na criação) e no endpoint dedicado
  `POST /api/v1/admin/users/<user_id>/force-password-reset`. **Nenhuma migration nova foi
  necessária** — o INSERT de `create_tenant()` passou a incluir `force_password_reset = true` no
  INSERT do admin do tenant, igual ao que `create_user()` já fazia.
- **Import**: `import secrets` movido para o topo do módulo (estava sendo importado localmente
  dentro de `create_user()`); removida a importação local redundante.
- **Confirmado**: `hash_password()` já usa bcrypt (`bcrypt.hashpw`) — não alterado. `temp_password`
  nunca é logado em nenhum `logger.*`/`print` do arquivo — só usado para hash e devolvido uma única
  vez no payload de resposta (`success({..., "temp_password": temp_password}, status=201)`).
- **Teste novo**: `services/api/tests/unit/admin/test_create_tenant_temp_password.py` — 4 casos:
  senha ≥16 chars e não derivada do slug (não contém o slug, não começa com `EpiMonitor@`, não
  termina em `2024!`); duas criações consecutivas geram senhas diferentes; INSERT do admin do
  tenant inclui `force_password_reset` setado; senha nunca aparece em nenhum log capturado
  (`caplog`).
- **Validação**: `ruff check services/api/` limpo; suíte completa
  `pytest services/api/tests/` → 3430 passed, 47 skipped (baseline conhecido), cobertura 66.82%
  (gate 60%).
- **security-review**: rodado sobre o diff antes do PR — ver corpo do PR para o resumo.
