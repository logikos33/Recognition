# Task 076 — [SEC] senha temporária de tenant previsível (achado #4)

**Status**: PENDING · **Risk**: security (P0 — credencial previsível)
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
