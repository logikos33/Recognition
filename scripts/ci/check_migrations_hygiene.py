"""
Guard-rails de higiene em infra/migrations/ (ADR-0021: colisão de numeração já
derrubou o startup da API uma vez, num incidente anterior e já resolvido —
este script existe para pegar a PRÓXIMA colisão antes que ela repita o problema).

Dois checks, independentes de banco de dados:

  1. Prefixo NNN duplicado entre arquivos infra/migrations/NNN_*.sql.
     Duplicatas HISTÓRICAS já existem (6 arquivos com prefixo "052", mergeados
     por PRs de feature paralelos no mesmo dia) e não podem ser renumeradas
     sem um PR de migration dedicado — migrations já aplicadas em produção são
     forward-only, renomear às cegas quebraria o rastro de deploy. Por isso
     existe uma baseline explícita (infra/migrations/.duplicate-prefix-baseline)
     com os PREFIXOS duplicados aceitos (um por linha, ex.: "052") — MESMO
     arquivo e MESMA semântica do pre-flight de infra/migrations/runner_core.py
     (que aborta o boot no loop com ledger, pós-cutover); este check dá o mesmo
     sinal em CI, cedo e sem banco, enquanto o loop legado (que não aborta)
     ainda é o de produção. O check falha apenas para prefixo duplicado NOVO
     fora da baseline — a baseline é dívida técnica registrada, não licença
     para criar mais colisões.

  2. Diretório migrations/ na raiz do repositório, além de infra/migrations/.
     O projeto usa infra/migrations/ como fonte única (ADR-0010); um segundo
     diretório de migrations já existiu no histórico do repo e foi removido
     (PRs #214/#215) — este check é a garantia de não-regressão.

Uso:
  python scripts/ci/check_migrations_hygiene.py
"""

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "infra" / "migrations"
BASELINE_FILE = MIGRATIONS_DIR / ".duplicate-prefix-baseline"
LEGACY_ROOT_MIGRATIONS_DIR = REPO_ROOT / "migrations"

PREFIX_RE = re.compile(r"^(\d+)_.+\.sql$")


def _load_baseline() -> set[str]:
    """Lê os PREFIXOS duplicados aceitos (mesma semântica de
    runner_core._load_baseline_duplicate_versions: uma versão por linha,
    ex.: "052"). Comentários com '#' e linhas vazias ignorados."""
    if not BASELINE_FILE.exists():
        return set()
    entries: set[str] = set()
    for raw_line in BASELINE_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entries.add(line)
    return entries


def check_duplicate_prefixes() -> list[str]:
    """Retorna mensagens de erro para prefixos NNN duplicados fora da baseline."""
    if not MIGRATIONS_DIR.is_dir():
        return [f"Diretório {MIGRATIONS_DIR.relative_to(REPO_ROOT)}/ não encontrado."]

    baseline = _load_baseline()

    by_prefix: dict[str, list[str]] = {}
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = PREFIX_RE.match(f.name)
        if not m:
            continue
        by_prefix.setdefault(m.group(1), []).append(f.name)

    errors: list[str] = []
    for prefix, files in sorted(by_prefix.items()):
        if len(files) < 2 or prefix in baseline:
            continue
        errors.append(
            f"Prefixo '{prefix}' duplicado ({len(files)} arquivos): {', '.join(files)}. "
            f"Não está na baseline (infra/migrations/.duplicate-prefix-baseline). "
            f"Renumere o(s) arquivo(s) novo(s) para um prefixo livre "
            f"(`ls infra/migrations/*.sql | sort | tail -1`) — a baseline cobre só a "
            f"dívida histórica já registrada, não novas colisões."
        )
    return errors


def check_no_duplicate_migrations_dir() -> list[str]:
    """Retorna erro se existir um segundo diretório migrations/ na raiz do repo."""
    if LEGACY_ROOT_MIGRATIONS_DIR.exists():
        return [
            f"Diretório legado {LEGACY_ROOT_MIGRATIONS_DIR.relative_to(REPO_ROOT)}/ existe "
            f"além de infra/migrations/. A fonte única de migrations é infra/migrations/ "
            f"(ADR-0010) — um segundo diretório é exatamente o tipo de duplicação que já "
            f"causou incidentes de numeração (ADR-0021). Remova o diretório legado ou mova "
            f"o conteúdo para infra/migrations/."
        ]
    return []


def main() -> int:
    errors = check_duplicate_prefixes() + check_no_duplicate_migrations_dir()

    if errors:
        print("Guard-rail de higiene de migrations FALHOU:\n")
        for e in errors:
            print(f"  - {e}\n")
        return 1

    print(
        "Guard-rail de higiene de migrations OK "
        "(sem duplicata de prefixo nova, sem diretório de migrations duplicado)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
