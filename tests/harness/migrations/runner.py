"""
Harness migration runner — CLI fino sobre infra/migrations/runner_core.py.

Este runner e railway_start.py:run_migrations() compartilham a MESMA implementação
(infra/migrations/runner_core.py) desde a unificação do mutirão de dívida técnica
(itens 3.2/3.3/3.4). Isso fecha a PEND que existia neste README:
"unificar o loop de apply do railway_start com o runner.py do harness".

Diferenças intencionais (cirúrgicas) que permanecem só aqui:
  1. DSN via --dsn arg ou HARNESS_DATABASE_URL (nunca DATABASE_URL, evita acidente em prod).
  2. --pass N apenas para identificar a passada nos logs.
  3. Exit code 1 se qualquer erro não-idempotente e não-legado ocorrer (mesma semântica de
     retorno que runner_core.run_legacy() já tinha).

Por padrão (sem MIGRATIONS_LEDGER_CUTOVER=1) roda o loop LEGADO — idêntico ao que este
arquivo fazia antes da unificação: idempotência por heurística de erro, tolera os 4 erros
legados conhecidos (KNOWN_LEGACY_ERRORS, reexportado de runner_core para uso dos testes:
ver test_legacy_tolerance_is_scoped_to_038 em test_migrations_harness.py), nunca aborta.

Com MIGRATIONS_LEDGER_CUTOVER=1, roda o loop novo (ledger + advisory xact lock) — usado
pela prova local do mutirão, não pelo job de CI (que continua testando o loop legado).

NÃO chamar infra/migrations/run_migrations.py — não existe mais neste repositório
(confirmado 2026-08-02; removido junto com a migrations/ raiz nos PRs #214/#215).
"""

import argparse
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS_DIR = str(_REPO_ROOT / "infra" / "migrations")
sys.path.insert(0, _MIGRATIONS_DIR)

import runner_core  # noqa: E402 — precisa do sys.path.insert acima

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HARNESS] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("harness.migrations")

# Reexportados de runner_core (fonte única) para preservar a API que os testes já importam
# (test_legacy_tolerance_is_scoped_to_038 faz `from runner import _is_known_legacy`).
KNOWN_LEGACY_ERRORS = runner_core.KNOWN_LEGACY_ERRORS


def _is_known_legacy(basename: str, error_text: str) -> bool:
    return runner_core.is_known_legacy(basename, error_text, KNOWN_LEGACY_ERRORS)


def _is_idempotent_error(error_text: str) -> bool:
    return runner_core.is_idempotent_error(error_text)


def run(dsn: str, pass_n: int) -> bool:
    """Aplica infra/migrations/*.sql em ordem, via runner_core (loop legado ou ledger).

    Retorna True se nenhum erro fatal ocorreu (loop legado) ou se a aplicação com ledger
    terminou sem abortar (loop novo).
    """
    return runner_core.run_migrations(
        dsn,
        migrations_dir=_MIGRATIONS_DIR,
        log=log,
        known_legacy_errors=KNOWN_LEGACY_ERRORS,
        pass_label=f"passada {pass_n}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Harness migration runner")
    parser.add_argument(
        "--dsn",
        default=os.environ.get("HARNESS_DATABASE_URL", ""),
        help="DSN PostgreSQL (ou HARNESS_DATABASE_URL)",
    )
    parser.add_argument("--pass", dest="pass_n", type=int, default=1, help="Número da passada (log)")
    args = parser.parse_args()

    if not args.dsn:
        log.error("DSN não informado. Use --dsn ou HARNESS_DATABASE_URL.")
        sys.exit(1)

    success = run(args.dsn, args.pass_n)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
