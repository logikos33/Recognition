# ADR-0018 — Counting DeepSORT Schema Rebuild

## Status: Aceito (2026-05-29)

## Contexto

A tabela `public.counting_sessions` em produção tinha schema de
fueling-validation (`truck_plate`, `bay_id`, `operator_count`,
`validated_by`), criada por um protótipo legado
(`migrations/004_rules_engine.sql`, diretório antigo antes de
`infra/migrations/`).

Esta tabela era zumbi: 0 rows, 0 referências no código atual. O mesmo
arquivo legado criou `session_events` (também zumbi).

O código atual de counting (`counting_repository`, `counting_bp`,
frontend `CountingPage` — "Contagem DeepSORT") espera schema DeepSORT
completamente diferente: `tenant_id`, `module_code`, `track_id`,
`class_name`, `session_id`, `UNIQUE(session_id, track_id)` para
anti-duplicata.

A tabela zumbi bloqueava as migrations 015 e 048:

- **015** tentava `CREATE TABLE IF NOT EXISTS counting_sessions` → no-op
  (tabela já existia com schema fueling) → `CREATE INDEX` em `tenant_id`
  (coluna ausente) → rollback total da migration inteira
- **048** tentava `ALTER ADD tenant_id` na tabela zumbi e referenciava
  `counting_events` (que nunca foi criada porque 015 sempre fazia
  rollback)

DeepSORT counting é necessário para produção: módulo Qualidade vai usar
contagem única (identificar pessoa/peça única), além do uso standalone
do módulo Counting.

## Decisão

DROP das tabelas zumbi (`counting_sessions` + `session_events`) e
recriação de `counting_sessions` + `counting_events` com schema DeepSORT
correto.

Esta é uma exceção consciente à regra arquitetural "migrations never
DROP" (que protege dados de produção). Justificativa: ambas as tabelas
têm 0 rows e 0 referências no código — não há dado nem dependência a
proteger. DROP confirmado via query direta ao banco de produção
(`railway run psql` com `DATABASE_PUBLIC_URL`).

Migrations 015 e 048 viram no-ops documentados (superseded por 049).
Não são deletadas para preservar integridade da sequência de migrations.

## Consequências

- `counting_bp` e frontend `CountingPage` passam a funcionar (eram
  500/erro de tabela)
- Módulo Qualidade pode usar `counting_sessions`/`counting_events` para
  contagem única
- Schema pronto para Fase 1 adicionar `site_id` (edge deployment)
- `session_events` removida (caso algum dia precise, recriar com schema
  definido)

## Verificação (banco de produção, 2026-05-29)

- `counting_sessions`: 0 rows, schema fueling, FK `camera_id → cameras`,
  `user_id → users`
- `session_events`: 0 rows
- Nenhuma FK externa apontando para `counting_sessions`
- `counting_repository` espera: `tenant_id`, `module_code`,
  `total_counts`, `track_id`, `class_name`, `confidence`,
  `last_seen_at`, `first_seen_at`
