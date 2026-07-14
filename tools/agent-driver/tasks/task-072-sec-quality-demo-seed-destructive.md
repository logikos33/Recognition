# Task 072 — [SEC] `quality/demo/seed` destrutivo sem gate de admin (achado #5)

**Status**: PENDING · **Risk**: security (P0 — apaga dados reais em produção)
**Branch**: fix/sec-quality-demo-seed-admin-gate (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #5 · **Relaciona**: ADR-0017 (tenant isolation), C-01.

## Problema (produção)
`POST /api/v1/quality/demo/seed?force=true` executa `DELETE FROM quality_reworks/quality_pieces/
quality_stations` e recria dados fake. Hoje **qualquer usuário autenticado** do tenant com o módulo
`quality` habilitado pode disparar — **apaga dados reais de produção**.

## Fix
- Exigir **role admin/superadmin** (não só JWT do tenant) no endpoint.
- `force=true` (destrutivo) só com superadmin + confirmação explícita; sem `force`, no-op se já houver dados.
- Considerar mover seed de demo pra trás de feature flag `demo_mode` (ADR-0035), OFF por padrão.

## Teste (falha-antes/passa-depois)
- Usuário comum do tenant → 403 (antes: 200 + apaga). Admin → ok. `force` sem superadmin → 403.

## Aceite
- Rota não destrói dado sem admin; teste prova o 403; ruff+pytest verde; PR pra develop; STOP p/ revisão.
