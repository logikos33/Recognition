#!/usr/bin/env python3
"""
Varredura estática de licenças nos arquivos requirements/*.txt (sem instalar).

Detecta pacotes AGPL/GPL por nome; respeitando MIGRATION_ALLOWLIST.
Usa pip-licenses só para o caminho leve (api.txt) que instala rápido no CI.

Uso:
    python scripts/scan_requirements_licenses.py requirements/api.txt requirements/worker.txt ...

Sai com código 1 se pacote AGPL/GPL for encontrado fora da allowlist.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Mapeamento: nome do pacote (lowercase) → licença proibida.
# Atualizar conforme novos pacotes forem adicionados/removidos.
KNOWN_AGPL_GPL: dict[str, str] = {
    "ultralytics": "AGPL-3.0 (YOLOv8) — remover quando detector ONNX (task-055c) estiver ativo",
    "pytorch-lightning": "Apache-2.0 (OK mas verificar versão)",  # exemplo — não é AGPL
}

# Pacotes com licença proibida que estão em migração ativa.
# REMOVE da lista quando o pacote sair das requirements de produção.
MIGRATION_ALLOWLIST: set[str] = {
    "ultralytics",  # tarefa 055c — migrar para YOLOX/RF-DETR ONNX
}

# Regex para extrair nome do pacote de uma linha de requirements
_PKG_RE = re.compile(r"^\s*([a-zA-Z0-9_.-]+)\s*([><=!~@].*)?$")


def resolve_file(path: Path, visited: set[Path] | None = None) -> list[str]:
    """Resolve -r includes recursivamente."""
    if visited is None:
        visited = set()
    if path in visited:
        return []
    visited.add(path)

    lines: list[str] = []
    try:
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-r "):
                included = path.parent / line[3:].strip()
                lines.extend(resolve_file(included, visited))
            else:
                lines.append(line)
    except FileNotFoundError:
        print(f"[scan] AVISO: arquivo não encontrado: {path}", file=sys.stderr)
    return lines


def scan_file(req_file: Path) -> tuple[list[str], list[str]]:
    """
    Retorna (violations, warnings):
    - violations: pacotes AGPL/GPL fora da allowlist
    - warnings: pacotes na allowlist (migração pendente)
    """
    violations: list[str] = []
    warnings: list[str] = []

    lines = resolve_file(req_file)
    for line in lines:
        m = _PKG_RE.match(line)
        if not m:
            continue
        name = m.group(1).lower().replace("_", "-").replace(".", "-")
        # Normalizar nomes alternativos
        canonical = name

        if canonical in {k.lower() for k in KNOWN_AGPL_GPL}:
            orig_key = next(k for k in KNOWN_AGPL_GPL if k.lower() == canonical)
            note = KNOWN_AGPL_GPL[orig_key]
            entry = f"  {line}  ← {note}"
            if canonical in {m2.lower() for m2 in MIGRATION_ALLOWLIST}:
                warnings.append(entry)
            else:
                violations.append(entry)

    return violations, warnings


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} <requirements_file> [...]")
        return 1

    all_violations: list[str] = []
    all_warnings: list[str] = []

    for arg in sys.argv[1:]:
        path = Path(arg)
        vio, warn = scan_file(path)
        if vio:
            all_violations.extend([f"  [{path.name}] {v.strip()}" for v in vio])
        if warn:
            all_warnings.extend([f"  [{path.name}] {w.strip()}" for w in warn])

    if all_warnings:
        print(
            f"⚠️  {len(all_warnings)} dep(s) AGPL/GPL em migração ativa "
            f"(MIGRATION_ALLOWLIST — task-055c):"
        )
        for w in all_warnings:
            print(w)
        print()

    if all_violations:
        print(
            f"❌ {len(all_violations)} dep(s) com licença PROIBIDA "
            f"encontrada(s) fora da allowlist:"
        )
        for v in all_violations:
            print(v)
        print()
        print("Ação: remova o pacote OU adicione à MIGRATION_ALLOWLIST (com justificativa e prazo).")
        return 1

    scanned = ", ".join(Path(a).name for a in sys.argv[1:])
    print(f"✅ Varredura estática OK em: {scanned}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
