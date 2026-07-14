# Task 075 — [SEC] `verification/queue` + `review` sem tenant_id (achado #14)

**Status**: PENDING · **Risk**: security (P0 — cross-tenant, verificar)
**Branch**: fix/sec-verification-tenant-isolation (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #14 · **Relaciona**: ADR-0017, C-01.

## Problema (produção)
`GET /api/v1/verification/queue`, `/queue/count` e `POST /api/v1/verification/<id>/review` não têm
`tenant_id` visível na assinatura, contrariando a regra do projeto. Primeiro **confirmar** se o
`VerificationService` filtra internamente; se não, é leitura/edição cross-tenant da fila de revisão.

## Fix
- Se o service não filtrar: adicionar `get_tenant_id()` em queue/count/review. Item de outro tenant no
  `review` → 404. O `human_review` grava o `tenant_id` correto.

## Teste (falha-antes/passa-depois)
- Fila só traz itens do tenant; review cross-tenant → 404; contagem por tenant. (Se já filtrava,
  adicionar o teste de regressão que prova o isolamento e fechar.)

## Aceite
- Isolamento por `tenant_id` confirmado/implementado + teste; ruff+pytest verde; PR develop; STOP.
