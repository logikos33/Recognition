# PEND-009 — Audit: WHERE tenant_id em queries críticas de quality

## Status
Aberto — 2026-05-28

## Contexto

ADR-0017 Camada 3 (defense in depth): queries de listagem em quality devem incluir
`WHERE tenant_id = %s` além do `SET search_path`. O schema isolation já garante
isolamento primário, mas queries sem filtro explícito ficam vulneráveis a bugs de
schema routing.

## Queries a auditar e corrigir

### Prioridade ALTA (retornam múltiplas linhas)

| Arquivo | Linha aprox | Query | Risco |
|---------|-------------|-------|-------|
| `gate_repository.py` | ~166 | `SELECT * FROM quality_pieces WHERE {where_clause}` | Listagem completa |
| `gate_repository.py` | ~389 | `SELECT * FROM quality_reworks WHERE {where_clause}` | Listagem completa |
| `gate_repository.py` | ~521 | `SELECT * FROM quality_stations ORDER BY station_code` | Full table scan |
| `routes.py` | ~406 | `SELECT COUNT(*) FROM quality_inspections {where_sql}` | Contagem sem escopo |
| `routes.py` | ~95 | `SELECT COUNT(*) FROM quality_retrain_suggestions WHERE status='pending'` | Contagem sem escopo |

### Prioridade MÉDIA (lookup por ID — risco menor)

| Arquivo | Linha aprox | Query |
|---------|-------------|-------|
| `routes.py` | ~569 | `SELECT clip_r2_key FROM quality_inspections WHERE id = %s` |
| `routes.py` | ~613 | `SELECT evidence_r2_key FROM quality_inspections WHERE id = %s` |
| `routes.py` | ~899 | `SELECT r2_key FROM quality_annotation_frames WHERE id = %s` |
| `routes.py` | ~1136 | `SELECT * FROM quality_training_jobs WHERE id = %s` |

## Padrão de correção

```python
# ANTES
cur.execute("SELECT * FROM quality_pieces WHERE station_id = %s", (station_id,))

# DEPOIS
cur.execute(
    "SELECT * FROM quality_pieces WHERE station_id = %s AND tenant_id = %s",
    (station_id, tenant_id)
)
```

## Pré-requisito

Verificar que `quality_pieces`, `quality_reworks`, `quality_stations`,
`quality_inspections`, `quality_retrain_suggestions` têm coluna `tenant_id`.
Se não tiverem, criar migration antes da correção de query.

## Responsável
Sprint de qualidade pós-Sprint 0.5

## Relacionado
- ADR-0017 Camada 3
- PEND-010: dead tables cleanup em public
