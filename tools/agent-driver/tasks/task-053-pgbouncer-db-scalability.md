# Task 053 — PgBouncer: Escalabilidade de Conexões DB

**Status**: PENDING
**Risk**: security (toca infra de banco)
**Branch**: feat/task-053-pgbouncer-db-scalability

## Objetivo

Adicionar PgBouncer como camada de connection pooling entre os serviços e o PostgreSQL Railway,
resolvendo o esgotamento de conexões identificado no harness de escala (task-052).

## Problema

- PostgreSQL Railway: limite de ~100 conexões simultâneas
- Com 28 câmeras × 2 workers (inference + quality) + API: pode ultrapassar limite
- Sintoma: `too many connections` errors sob carga

## Entregáveis

- [ ] ADR-0029: decisão de adicionar PgBouncer ao stack
- [ ] `services/pgbouncer/` — configuração Docker + railway.toml
- [ ] `services/pgbouncer/pgbouncer.ini` — pool_mode=transaction, max_client_conn=200, pool_size=20
- [ ] Atualizar `DATABASE_URL` dos serviços para apontar ao PgBouncer (não direto ao PG)
- [ ] Migration: nenhuma (mudança de infra apenas)
- [ ] Teste de carga: 28 câmeras simultâneas sem `too many connections`

## Referências

- `docs/architecture/BENCHMARK_ORIN_NX_DETECTOR.md`
- `docs/decisions/adr/0022-db-connection-scalability-and-messaging.md`
- Ponto de degradação: ver `docs/evidence/e2e-scale/REPORT.md` (task-052)

## Gate

Gate de segurança obrigatório: teste que falha-antes/passa-depois com 28 câmeras.
Revisão humana antes de merge (risk: security).
