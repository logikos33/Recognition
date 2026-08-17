"""
Docs & ADR provenance gate — falha o CI quando a documentação contradiz o
próprio registro de decisões.

Nasceu de seis relatos que afirmaram fatos falsos numa única semana (CLAUDE.md
descrevendo `backend/` e 13 microserviços inexistentes; evidência dita
"cloud-first" já superseded; classe fantasma "Sem Capacete" que nunca existiu no
banco; duas ADR-0043; a 0057 referenciada mas ausente). Corrigir à mão sem gate
garante o sétimo. Contexto: docs/decisions/PROCEDENCIA_DE_RELATOS.md.

Seis regras — cada violação imprime ARQUIVO: problema:
  1. Dois ADRs compartilham número.
  2. Um ADR não tem Status entre os valores válidos.
  3. Buraco na sequência de ADRs (reservar um número = criar um ADR placeholder
     com `Status: Reservado`; assim o buraco fica DECLARADO, não silencioso).
  4. CLAUDE.md cita um ADR que está Superseded.
  5. O título interno (`# ADR-NNNN`) não bate com o número do arquivo.
  6. A taxonomia RVB (bloco marcado `<!-- RVB-EPI-CLASSES -->`) diverge entre
     documentos — extraída de cada um e comparada, sem opinar sobre qual está
     certa. Foi a divergência entre docs que pôs "Sem Capacete" em 3 rodadas.

Sem dependências externas — stdlib only. O gate de licença (ADR-0043) vale para
a ferramenta do próprio gate: nada de AGPL, nada de pip install.

Uso:
  python scripts/ci/check_docs_gate.py                # falha (exit 1) se violação
  python scripts/ci/check_docs_gate.py --report-only  # imprime, não falha
"""
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADR_DIR = ROOT / "docs" / "decisions" / "adr"
CLAUDE_MD = ROOT / "CLAUDE.md"

_ADR_FILE_RE = re.compile(r"^(\d{4})-.+\.md$")
# Título aceita as duas convenções vivas no repo: "# ADR-0017 —" e "# ADR 0001 —".
_ADR_TITLE_RE = re.compile(r"^#\s+ADR[-\s]0*(\d{1,4})\b", re.MULTILINE)
# Status aceita as duas convenções: "**Status:** X" inline e "## Status" (Nygard)
# com o valor na linha seguinte. Extraído por _extract_status, não por um regex só.
_STATUS_LINE_RE = re.compile(r"^\*{0,2}Status\*{0,2}\s*:?\s*(.*)$", re.IGNORECASE)
# Banner de supersede no corpo — "Parcialmente superseded" (parcial) NÃO conta.
_SUPERSEDED_BANNER_RE = re.compile(r"(?<!almente\s)superseded\s+por\s+ADR-\d+", re.IGNORECASE)
_ADR_CITATION_RE = re.compile(r"ADR-(\d{3,4})")
_CLASS_BLOCK_RE = re.compile(
    r"<!--\s*RVB-EPI-CLASSES:start.*?-->(.*?)<!--\s*RVB-EPI-CLASSES:end\s*-->",
    re.DOTALL | re.IGNORECASE,
)

# Primeiro token do Status, sem acento e minúsculo. Aceita as variantes reais em
# uso (Aceito/Aceita/Accepted, Proposta, ...) + os estados canônicos.
VALID_STATUS = {
    "proposta", "proposed", "aceito", "aceita", "accepted", "aprovada",
    "aprovado", "superseded", "substituido", "substituida", "rejeitado",
    "rejeitada", "rejected", "reservado", "reservada", "deprecated",
    "descontinuado", "descontinuada", "indeterminado", "indeterminada",
}
SUPERSEDED_TOKENS = {"superseded", "substituido", "substituida"}


def _deburr(text: str) -> str:
    """Minúsculo sem acentos, para comparar Status de forma robusta."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _status_token(status_line: str) -> str:
    """Primeiro token significativo do Status (`Aceito. **Parc...` -> `aceito`)."""
    first = re.split(r"[·|(.,\s]", status_line.strip(), maxsplit=1)[0]
    return _deburr(first).strip("*: ")


def _extract_status(text: str) -> str | None:
    """Valor do Status em qualquer das convenções de ADR do repo.

    Reconhece `**Status:** X`, `## Status: X` e `## Status` seguido do valor na
    próxima linha não-vazia. Remove marcadores de heading/lista/citação antes.
    """
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        stripped = raw.lstrip("#>*- \t")
        m = _STATUS_LINE_RE.match(stripped)
        if not m:
            continue
        value = m.group(1).strip(" *")
        if value:
            return value
        for nxt in lines[i + 1:]:  # heading "## Status" — valor na linha seguinte
            if nxt.strip():
                return nxt.strip(" *")
        return None
    return None


class Adr:
    def __init__(self, path: pathlib.Path, file_num: int):
        self.path = path
        self.file_num = file_num
        text = path.read_text(encoding="utf-8")
        title = _ADR_TITLE_RE.search(text)
        self.internal_num = int(title.group(1)) if title else None
        self.status_raw = _extract_status(text)
        self.status_token = _status_token(self.status_raw) if self.status_raw else None
        self.superseded = self.status_token in SUPERSEDED_TOKENS or bool(
            _SUPERSEDED_BANNER_RE.search(text)
        )

    def rel(self) -> str:
        return self.path.relative_to(ROOT).as_posix()


def _load_adrs() -> list[Adr]:
    adrs = []
    for path in sorted(ADR_DIR.glob("*.md")):
        m = _ADR_FILE_RE.match(path.name)
        if not m:
            continue  # RECONCILIACAO_*.md e outros não-ADR
        num = int(m.group(1))
        if num == 0:
            continue  # 0000-template.md
        adrs.append(Adr(path, num))
    return adrs


def _iter_markdown(root: pathlib.Path):
    skip = {"node_modules", ".git", "dist", "build", "venv", ".venv", "__pycache__"}
    for path in root.rglob("*.md"):
        if not any(part in skip for part in path.parts):
            yield path


def _class_set(block: str) -> frozenset[str]:
    items = re.findall(r"^\s*[-*]\s+(.+?)\s*$", block, re.MULTILINE)
    return frozenset(_deburr(i) for i in items if i.strip())


def check() -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    adrs = _load_adrs()
    by_num: dict[int, list[Adr]] = {}
    for adr in adrs:
        by_num.setdefault(adr.file_num, []).append(adr)

    # Regra 1 — número duplicado.
    for num, group in sorted(by_num.items()):
        if len(group) > 1:
            files = ", ".join(a.path.name for a in group)
            violations.append(("docs/decisions/adr/", f"ADR-{num:04d} duplicado em: {files}"))

    # Regra 2 e 5 — status inválido / título interno divergente.
    for adr in adrs:
        if adr.status_token not in VALID_STATUS:
            shown = adr.status_raw if adr.status_raw else "(ausente)"
            violations.append((adr.rel(), f"Status inválido ou ausente: {shown!r} (válidos: {', '.join(sorted(VALID_STATUS))})"))
        if adr.internal_num is None:
            violations.append((adr.rel(), "sem título interno no formato '# ADR-NNNN'"))
        elif adr.internal_num != adr.file_num:
            violations.append((adr.rel(), f"título interno diz ADR-{adr.internal_num:04d} mas o arquivo é {adr.file_num:04d}"))

    # Regra 3 — buraco na sequência (placeholder Reservado preenche o buraco).
    if by_num:
        present = set(by_num)
        for n in range(1, max(present) + 1):
            if n not in present:
                violations.append((
                    "docs/decisions/adr/",
                    f"ADR-{n:04d} ausente na sequência — crie um placeholder "
                    f"(NNNN-*.md com 'Status: Reservado') para declarar o número queimado",
                ))

    # Regra 4 — CLAUDE.md cita um ADR Superseded.
    superseded_nums = {a.file_num for a in adrs if a.superseded}
    if CLAUDE_MD.exists():
        cited = {int(n) for n in _ADR_CITATION_RE.findall(CLAUDE_MD.read_text(encoding="utf-8"))}
        for num in sorted(cited & superseded_nums):
            violations.append((
                "CLAUDE.md",
                f"cita ADR-{num:04d}, que está Superseded — aponte para o ADR que o substitui",
            ))

    # Regra 6 — taxonomia RVB diverge entre documentos (extrai de cada, compara).
    taxonomies: list[tuple[str, frozenset[str]]] = []
    for path in _iter_markdown(ROOT):
        m = _CLASS_BLOCK_RE.search(path.read_text(encoding="utf-8"))
        if m:
            taxonomies.append((path.relative_to(ROOT).as_posix(), _class_set(m.group(1))))
    if len({t[1] for t in taxonomies}) > 1:
        files = ", ".join(f for f, _ in taxonomies)
        detail = " | ".join(f"{f}: {{{', '.join(sorted(s))}}}" for f, s in taxonomies)
        violations.append((
            f"{files}",
            f"taxonomia RVB (bloco RVB-EPI-CLASSES) diverge entre documentos — {detail}",
        ))

    return violations


def main() -> int:
    report_only = "--report-only" in sys.argv
    violations = check()
    if violations:
        print("DOCS GATE FAILED — documentação contradiz o registro de decisões:")
        for where, problem in violations:
            print(f"  {where}: {problem}")
        print()
        print("Cada relato é hipótese até ser verificado contra código, git ou banco.")
        print("Ver docs/decisions/PROCEDENCIA_DE_RELATOS.md.")
        return 0 if report_only else 1
    print("Docs gate PASSED — ADRs, citações e taxonomia RVB consistentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
