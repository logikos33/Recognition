"""
License gate — verifica que nenhum pacote AGPL/copyleft forte existe:
  1. nos requirements de produção servida (api, worker, inference, celery-worker);
  2. via `import`/`from ... import` de pacotes AGPL no código-fonte servido
     (services/api/app, services/inference) — task-081/ADR-0043. Um `import
     ultralytics` pode passar despercebido no requirements.txt (dependência
     transitiva, instalação manual, etc.) mas ainda assim rodar em produção.

Uso:
  python scripts/check_license_gate.py               # falha se violação
  python scripts/check_license_gate.py --report-only # só imprime, não falha
"""
import ast
import pathlib
import re
import sys

# Pacotes com licença AGPL ou copyleft forte incompatível com uso comercial
AGPL_PACKAGES: frozenset[str] = frozenset(
    {
        "ultralytics",
        "agpllib",
        "copyleft-example",
    }
)

# Requirements que fazem parte do caminho de produção servido
SERVING_REQ_FILES: list[str] = [
    "requirements/base.txt",
    "requirements/api.txt",
    "requirements/worker.txt",
    "requirements/inference.txt",
    "requirements/celery-worker.txt",
    "services/inference/requirements.txt",
]

# Requirements de treino/tooling — excluídos do gate (nunca servidos)
_EXCLUDED: frozenset[str] = frozenset(
    {
        "requirements/assistant-training.txt",
    }
)

# Diretórios escaneados por import (task-081 + task "treino não pode
# mentir"). training/ e scripts/ entraram nesta task: o scan de imports
# nunca cobria o código de treino em si (só o servido) — um `import
# ultralytics` num script de treino esquecido passava despercebido. Não são
# "servidos" no sentido do ADR-0043, mas são código que RODA neste repo (CI,
# runners remotos) e merecem o mesmo scan AST — zero AGPL em qualquer lugar,
# não só no caminho de inferência.
SERVING_SOURCE_DIRS: list[str] = [
    "services/api/app",
    "services/inference/inference",
    "training",
    "scripts",
]

# Exceções conhecidas e datadas — cada uma amarrada a uma task que a remove.
# NÃO adicionar entradas novas aqui sem uma task de remoção associada
# (ADR-0043 é zero-AGPL no servido; isto é dívida documentada, não uma saída
# permanente). VAZIA desde task-080 (2026-07-15): o baseline de 3 violações
# do dia em que o scanner entrou (task-081) foi zerado por task-079 + task-080.
KNOWN_IMPORT_EXCEPTIONS: frozenset[str] = frozenset()


def _iter_python_files(root: pathlib.Path, rel_dir: str) -> list[pathlib.Path]:
    base = root / rel_dir
    if not base.exists():
        return []
    return sorted(base.rglob("*.py"))


def _imported_top_level_packages(source: str) -> set[str]:
    """Retorna o nome do pacote top-level de cada import (`import x.y` → `x`)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                packages.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                packages.add(node.module.split(".")[0])
    return packages


def _check_source_imports(root: pathlib.Path) -> list[tuple[pathlib.Path, str]]:
    """Escaneia SERVING_SOURCE_DIRS por imports de AGPL_PACKAGES.

    Arquivos em KNOWN_IMPORT_EXCEPTIONS são pulados (dívida documentada,
    ver task associada em cada entrada).
    """
    violations: list[tuple[pathlib.Path, str]] = []
    for rel_dir in SERVING_SOURCE_DIRS:
        for path in _iter_python_files(root, rel_dir):
            rel_path = path.relative_to(root).as_posix()
            if rel_path in KNOWN_IMPORT_EXCEPTIONS:
                continue
            packages = _imported_top_level_packages(path.read_text())
            hit = packages & AGPL_PACKAGES
            if hit:
                violations.append((path, f"import de pacote AGPL: {', '.join(sorted(hit))}"))
    return violations


def _pkg_name(line: str) -> str:
    """Extrai nome do pacote de uma linha de requirements."""
    line = line.strip()
    return re.split(r"[>=<!\[;@ ]", line)[0].lower().replace("-", "_")


def _check_file(path: pathlib.Path, checked: set[str] | None = None) -> list[tuple[pathlib.Path, str]]:
    if checked is None:
        checked = set()
    key = str(path.resolve())
    if key in checked:
        return []
    checked.add(key)

    violations: list[tuple[pathlib.Path, str]] = []
    if not path.exists():
        return violations

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            included = path.parent / line[3:].strip()
            if str(included) not in _EXCLUDED:
                violations.extend(_check_file(included, checked))
            continue
        pkg = _pkg_name(line)
        if pkg in AGPL_PACKAGES:
            violations.append((path, line))

    return violations


def main() -> int:
    report_only = "--report-only" in sys.argv

    root = pathlib.Path(__file__).parent.parent
    all_violations: list[tuple[pathlib.Path, str]] = []

    for rel in SERVING_REQ_FILES:
        all_violations.extend(_check_file(root / rel))

    import_violations = _check_source_imports(root)

    if all_violations or import_violations:
        print("LICENSE GATE FAILED — pacotes AGPL/copyleft encontrados no caminho servido:")
        for path, line in all_violations:
            print(f"  {path.relative_to(root)}: {line}")
        for path, reason in import_violations:
            print(f"  {path.relative_to(root)}: {reason}")
        print()
        print("Ação: substituir por alternativa Apache 2.0/MIT — não há mais requirements de treino isento do gate.")
        print("Se for uma dívida conhecida com task de remoção associada, adicionar a KNOWN_IMPORT_EXCEPTIONS.")
        if not report_only:
            return 1
        return 0

    print("License gate PASSED — nenhum pacote AGPL nos requirements/imports de produção servida.")
    if KNOWN_IMPORT_EXCEPTIONS:
        print(f"  ({len(KNOWN_IMPORT_EXCEPTIONS)} exceção(ões) conhecida(s) e datada(s) — ver KNOWN_IMPORT_EXCEPTIONS)")
    _print_notice(root)
    return 0


def _print_notice(root: pathlib.Path) -> None:
    notice_path = root / "THIRD_PARTY_NOTICES.txt"
    notice_path.write_text(
        "THIRD-PARTY SOFTWARE NOTICES\n"
        "============================\n"
        "Este projeto usa os seguintes pacotes de terceiros nos requirements de produção:\n\n"
        "requirements/base.txt, api.txt, worker.txt, inference.txt, celery-worker.txt\n\n"
        "Licenças resumidas por tipo:\n"
        "  Apache 2.0 / MIT / BSD: Flask, psycopg2, boto3, redis, celery, onnxruntime,\n"
        "                          opencv-python-headless, numpy, Pillow, torch,\n"
        "                          torchvision, cryptography, pydantic, structlog, ...\n\n"
        "  Zero pacotes copyleft (AGPL/GPL) em requirements de produção OU em\n"
        "  requirements/training.txt — removido (task \"treino não pode mentir\"):\n"
        "  ultralytics era usado só pelo fluxo de treino legado (Roboflow/\n"
        "  provision_and_train.sh), deletado nesta task junto com o pacote.\n\n"
        "Para lista completa: pip-licenses --from=classifier (requer pip install pip-licenses)\n"
    )
    print(f"THIRD_PARTY_NOTICES.txt gerado em {notice_path}")


if __name__ == "__main__":
    sys.exit(main())
