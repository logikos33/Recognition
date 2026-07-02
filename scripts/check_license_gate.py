"""
License gate — verifica que nenhum pacote AGPL/copyleft forte existe nos
requirements de produção servida (api, worker, inference, celery-worker).

Uso:
  python scripts/check_license_gate.py               # falha se violação
  python scripts/check_license_gate.py --report-only # só imprime, não falha
"""
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
]

# Requirements de treino/tooling — excluídos do gate (nunca servidos)
_EXCLUDED: frozenset[str] = frozenset(
    {
        "requirements/training.txt",
        "requirements/assistant-training.txt",
        "requirements/pre-annotation.txt",
    }
)


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

    if all_violations:
        print("LICENSE GATE FAILED — pacotes AGPL/copyleft encontrados no caminho servido:")
        for path, line in all_violations:
            print(f"  {path.relative_to(root)}: {line}")
        print()
        print("Ação: mover para requirements/training.txt (apenas treino) ou substituir por alternativa Apache 2.0.")
        if not report_only:
            return 1
        return 0

    print("License gate PASSED — nenhum pacote AGPL nos requirements de produção servida.")
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
        "  Licenças copyleft (APENAS em requirements/training.txt — não servido):\n"
        "    ultralytics>=8.0.0 — AGPL-3.0 (usado somente em treinamento offline/Vast.ai)\n\n"
        "Para lista completa: pip-licenses --from=classifier (requer pip install pip-licenses)\n"
    )
    print(f"THIRD_PARTY_NOTICES.txt gerado em {notice_path}")


if __name__ == "__main__":
    sys.exit(main())
