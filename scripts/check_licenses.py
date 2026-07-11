#!/usr/bin/env python3
"""
License gate — task-055a.

Verifica que nenhum pacote AGPL/GPL/copyleft forte está nos
requirements de produção (api, inference, worker).

Uso:
    pip-licenses --format=json --output-file=licenses.json
    python scripts/check_licenses.py licenses.json [--warn-only]

Exit code 1 se pacotes proibidos forem encontrados (sem --warn-only).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Licenças que bloqueiam SaaS fechado.
# LGPL é permitida (psycopg2, FFmpeg) — confirmar com advogado (ver task-055).
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "GNU General Public License v3",
    "GNU General Public License v2",
    "GNU Affero General Public License",
    "GPLv3",
    "GPLv2",
    "AGPLv3",
    "AGPL",
    "GPL-3",
    "GPL-2",
)

# Pacotes explicitamente em migração — removidos do caminho servido em task-055c.
# Listar aqui permite rastrear o débito; remover da lista quando sair das requirements.
MIGRATION_ALLOWLIST: set[str] = {
    # ultralytics (AGPL-3.0) está em requirements/worker.txt e requirements/inference.txt
    # mas será removido quando o detector ONNX (A1/055c) for mergeado.
    # NÃO adicionar novos pacotes aqui sem aprovação.
    "ultralytics",
}


def is_forbidden(license_str: str) -> bool:
    """Retorna True se a licença é AGPL/GPL (copyleft forte)."""
    for sub in FORBIDDEN_SUBSTRINGS:
        if sub.lower() in license_str.lower():
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="License gate — copyleft check")
    parser.add_argument("licenses_json", help="JSON gerado por pip-licenses --format=json")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Reportar mas não falhar (usar só durante migração)",
    )
    args = parser.parse_args(argv)

    path = Path(args.licenses_json)
    if not path.exists():
        print(f"[license-gate] ERRO: arquivo não encontrado: {path}", file=sys.stderr)
        return 1

    packages: list[dict] = json.loads(path.read_text())

    violations: list[str] = []
    in_migration: list[str] = []

    for pkg in packages:
        name = pkg.get("Name", "")
        version = pkg.get("Version", "")
        lic = pkg.get("License", "Unknown")

        if not is_forbidden(lic):
            continue

        entry = f"  {name}=={version}: {lic}"
        if name.lower() in {m.lower() for m in MIGRATION_ALLOWLIST}:
            in_migration.append(entry)
        else:
            violations.append(entry)

    if in_migration:
        print(
            f"⚠️  {len(in_migration)} pacote(s) AGPL/GPL em migração pendente "
            f"(task-055c — ver MIGRATION_ALLOWLIST):"
        )
        for line in in_migration:
            print(line)
        print()

    if violations:
        print(f"❌ {len(violations)} pacote(s) com licença proibida (AGPL/GPL) detectado(s):")
        for line in violations:
            print(line)
        print()
        print(
            "Para corrigir: remova o pacote das requirements de produção "
            "ou adicione à MIGRATION_ALLOWLIST enquanto a migração não é concluída."
        )
        if args.warn_only:
            print("[license-gate] --warn-only ativo: não falhando o build.")
            return 0
        return 1

    total = len(packages)
    print(
        f"✅ Todos os {total} pacotes verificados têm licença permissiva. "
        f"Nenhum AGPL/GPL no caminho de produção."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
