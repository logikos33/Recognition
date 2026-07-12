---
title: "Harness: assert final-state das migrations toleradas (038/039)"
commit_message: "test(harness): assert que operations e operation_results existem após 2 passadas"
eval: harness
---

# Harness — assert de auto-correção das migrations legadas

## Objetivo

Provar, via teste, que as migrations 038 e 039 — toleradas como legadas pelo runner
porque falham em banco virgem — **autocorrigem** ao final das 2 passadas. Hoje o
harness aceita o erro em silêncio; este teste fecha o ciclo: "tolerei o erro
porque o estado final está correto. Prove."

## Arquivos no escopo

- `tests/harness/migrations/test_migrations_harness.py` (adicionar 1 teste parametrizado)

## Mudança

No fim de `test_migrations_harness.py`, adicionar:

```python
LEGACY_TOLERATED_TABLES = ["operations", "operation_results"]


@pytest.mark.parametrize("table_name", LEGACY_TOLERATED_TABLES)
def test_legacy_tolerated_migrations_autocorrect(pg_conn, table_name):
    """Migrations 038/039 falham em banco virgem (toleradas), mas o estado final
    tem que existir — 047 cria operations, 048 cria operation_results.

    Se este teste falhar, a tolerância em KNOWN_LEGACY_ERRORS está mascarando
    um bug real: o estado não autocorrige.
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        row = cur.fetchone()
    assert row["cnt"] == 1, (
        f"viola C-04: public.{table_name} ausente — a tolerância de erro legado "
        f"em runner.KNOWN_LEGACY_ERRORS está mascarando bug real (não autocorrige)."
    )
```

Usar a fixture `pg_conn` já existente em `conftest.py`. Não criar nova fixture.

## Critérios de aceitação

- [ ] Teste adicionado ao arquivo correto, no fim, mantendo o padrão dos outros.
- [ ] Eval `harness` verde (16 + 2 = 18 testes verdes).
- [ ] Nenhum outro arquivo tocado.
- [ ] Diff não toca paths protegidos.

## Eval

`bash tests/harness/migrations/run.sh` — exit 0, com os 2 novos asserts passando.

## Checkpoints

- Só PR pra `develop`. Sem banco de produção. Sem tocar `infra/migrations/` (apenas observamos).
