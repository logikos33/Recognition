#!/usr/bin/env python3
"""Registro de decisões: um arquivo por decisão.

O registro nasceu como um único `docs/REGISTRO_DE_DECISOES.md` append-only. Com
duas sessões trabalhando em paralelo, todo append cai na mesma região do mesmo
arquivo: foram 3 colisões de número `D-` em 3 rodadas, e cada uma custou uma
resolução de conflito manual num arquivo de 3.500 linhas.

Um arquivo por decisão (como as ADRs) troca esse conflito por outro muito menor:
duas sessões que escolham o mesmo número produzem dois *arquivos*, e a resolução
é renomear um deles e regerar o índice.

Subcomandos:
  split   — migração única: quebra o monólito em docs/decisions/D-NNN-slug.md
  index   — regera docs/decisions/INDICE.md a partir dos arquivos
  new     — cria o próximo D- livre (imprime o caminho)
  check   — falha se houver número duplicado ou índice desatualizado
  selftest— exercita o parser em fixtures embutidas

stdlib only — o gate de licença vale para a ferramenta também.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
MONOLITO = ROOT / "docs" / "REGISTRO_DE_DECISOES.md"
DEST = ROOT / "docs" / "decisions"
INDICE = DEST / "INDICE.md"

# "### D-01 · Título" — separador · — ou : ; número com ou sem zero à esquerda.
_ENTRY_RE = re.compile(r"^###\s+D-0*(\d{1,4})\s*[·—:-]\s*(.+?)\s*$")
_SECTION_RE = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_FILE_RE = re.compile(r"^D-(\d{3})-.+\.md$")
_H1_RE = re.compile(r"^#\s+D-0*(\d{1,4})\s*[·—:-]\s*(.+?)\s*$", re.MULTILINE)
# Status: emoji do vocabulário do registro (✅ 🔄 ⏸ ↩ ❌ 📌) + a palavra seguinte.
# ⚠️/🛑 ficam de fora: no corpo eles marcam ênfase, não estado.
_STATUS_RE = re.compile(r"([✅🔄⏸↩❌📌])\s*([A-Za-zÀ-ÿ]*)")
_DATA_RE = re.compile(r"\b(\d{2}/\d{2}(?:/\d{2,4})?|\d{4}-\d{2}-\d{2})\b")


def _deburr(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def slugify(title: str, maxlen: int = 60) -> str:
    """Título -> slug ascii-kebab. Emoji e pontuação viram separador."""
    slug = re.sub(r"[^a-z0-9]+", "-", _deburr(title).lower()).strip("-")
    if len(slug) > maxlen:
        slug = slug[:maxlen].rsplit("-", 1)[0]
    return slug or "sem-titulo"


def parse_monolito(text: str) -> list[dict]:
    """Extrai as entradas `### D-NN · …` com o corpo VERBATIM.

    Uma entrada termina no próximo heading `##`/`###` ou no fim do arquivo. As
    linhas `---` e as vazias do rodapé são aparadas — não são conteúdo.
    Conteúdo que não é entrada `D-` (constatações, notas de método) permanece
    apenas no monólito, que é congelado inteiro.
    """
    lines = text.splitlines()
    entries: list[dict] = []
    section = ""
    current: dict | None = None
    for line in lines:
        sec = _SECTION_RE.match(line)
        if sec:
            if current:
                entries.append(current)
                current = None
            section = sec.group(1)
            continue
        entry = _ENTRY_RE.match(line)
        if entry:
            if current:
                entries.append(current)
            current = {
                "num": int(entry.group(1)),
                "title": entry.group(2),
                "section": section,
                "body": [],
            }
            continue
        if line.startswith("### ") and current:  # heading não-D- fecha a entrada
            entries.append(current)
            current = None
            continue
        if current is not None:
            current["body"].append(line)
    if current:
        entries.append(current)

    for e in entries:
        body = e.pop("body")
        while body and body[-1].strip() in ("", "---"):
            body.pop()
        e["body"] = "\n".join(body).strip("\n")
    return entries


def _meta(body: str) -> tuple[str, str]:
    """(data, status) da primeira linha de metadados do corpo.

    A linha `**Seção:** … **Origem:** …` é cabeçalho que o split acrescenta —
    não é metadado da decisão, e é pulada antes de procurar data e status.
    """
    uteis = [
        ln
        for ln in body.splitlines()
        if ln.strip() and not ln.lstrip().startswith(("**Seção:**", "**Origem:**", ">"))
    ]
    head = "\n".join(uteis[:2])
    data = _DATA_RE.search(head)
    status = _STATUS_RE.search(head)
    return (
        data.group(1) if data else "—",
        (status.group(1) + (" " + status.group(2) if status.group(2) else "")).strip()
        if status
        else "—",
    )


def render(entry: dict, origem: str) -> str:
    head = f"# D-{entry['num']:03d} · {entry['title']}\n"
    if entry.get("section"):
        head += f"\n**Seção:** {entry['section']}"
        head += f" · **Origem:** `{origem}`\n"
    else:
        head += f"\n**Origem:** `{origem}`\n"
    return f"{head}\n{entry['body']}\n"


def read_files() -> list[dict]:
    out = []
    for path in sorted(DEST.glob("D-*.md")):
        if not _FILE_RE.match(path.name):
            continue
        text = path.read_text(encoding="utf-8")
        m = _H1_RE.search(text)
        if not m:
            raise SystemExit(f"{path}: sem H1 no formato `# D-NNN · título`")
        num = int(m.group(1))
        if num != int(path.name[2:5]):
            raise SystemExit(f"{path}: H1 diz D-{num:03d}, nome do arquivo diz outro número")
        body = text[m.end():]
        data, status = _meta(body)
        out.append({"num": num, "title": m.group(2), "path": path, "data": data, "status": status})
    return sorted(out, key=lambda e: e["num"])


def build_index(files: list[dict]) -> str:
    linhas = [
        "# Índice de Decisões — Recognition",
        "",
        "<!-- GERADO por tools/decisoes.py index — não edite à mão. -->",
        "",
        "Uma decisão por arquivo (`docs/decisions/D-NNN-slug.md`). Convenção e motivo:",
        "[`README.md`](./README.md). Histórico congelado: [`../REGISTRO_DE_DECISOES.md`](../REGISTRO_DE_DECISOES.md).",
        "",
        f"**{len(files)} decisões** · última: D-{files[-1]['num']:03d}" if files else "Nenhuma decisão.",
        "",
        "| # | Decisão | Data | Status |",
        "|---|---|---|---|",
    ]
    for f in files:
        titulo = f["title"].replace("|", "\\|")
        linhas.append(
            f"| [D-{f['num']:03d}](./{f['path'].name}) | {titulo} | {f['data']} | {f['status']} |"
        )
    return "\n".join(linhas) + "\n"


def cmd_split(args) -> int:
    entries = parse_monolito(MONOLITO.read_text(encoding="utf-8"))
    if not entries:
        raise SystemExit(f"{MONOLITO}: nenhuma entrada `### D-NN ·` encontrada")
    DEST.mkdir(parents=True, exist_ok=True)
    origem = MONOLITO.relative_to(ROOT).as_posix()
    escritos = 0
    for e in entries:
        path = DEST / f"D-{e['num']:03d}-{slugify(e['title'])}.md"
        if path.exists() and not args.force:
            print(f"pulado (já existe): {path.name}")
            continue
        path.write_text(render(e, origem), encoding="utf-8")
        escritos += 1
    print(f"{escritos} arquivo(s) escrito(s) de {len(entries)} entrada(s) em {DEST}")
    return 0


def cmd_index(_args) -> int:
    INDICE.write_text(build_index(read_files()), encoding="utf-8")
    print(f"índice regerado: {INDICE}")
    return 0


def cmd_new(args) -> int:
    files = read_files()
    num = (files[-1]["num"] + 1) if files else 1
    path = DEST / f"D-{num:03d}-{slugify(args.titulo)}.md"
    if path.exists():
        raise SystemExit(f"{path} já existe")
    path.write_text(
        f"# D-{num:03d} · {args.titulo}\n\n**Data:** AAAA-MM-DD · **Status:** ✅ vigente\n\n"
        "Contexto em uma linha. A decisão. Por quê — e o que foi descartado.\n",
        encoding="utf-8",
    )
    print(path)
    return 0


def check(report_only: bool = False) -> list[str]:
    problemas = []
    vistos: dict[int, pathlib.Path] = {}
    files = read_files()
    for f in files:
        if f["num"] in vistos:
            problemas.append(
                f"D-{f['num']:03d}: número duplicado — {vistos[f['num']].name} e {f['path'].name}"
            )
        vistos[f["num"]] = f["path"]
    esperado = build_index(files)
    atual = INDICE.read_text(encoding="utf-8") if INDICE.exists() else ""
    if atual != esperado:
        problemas.append("INDICE.md desatualizado — rode `python tools/decisoes.py index`")
    return problemas


def cmd_check(args) -> int:
    problemas = check()
    for p in problemas:
        print(f"docs/decisions: {p}")
    if problemas and not args.report_only:
        return 1
    if not problemas:
        print("docs/decisions: OK")
    return 0


def cmd_selftest(_args) -> int:
    fixture = """# topo
## Seção A

### D-01 · Primeira · com ponto
**02/08 · Vitor · ✅ vigente**

Corpo um.

### Constatação · não é decisão
lixo que não deve virar arquivo

---

## Seção B

### D-175 · Última
**Status:** 🔄 em execução · **Data:** 2026-08-18

Corpo dois.

---
"""
    e = parse_monolito(fixture)
    assert [x["num"] for x in e] == [1, 175], e
    assert e[0]["title"] == "Primeira · com ponto", e[0]["title"]
    assert e[0]["section"] == "Seção A" and e[1]["section"] == "Seção B"
    assert e[0]["body"] == "**02/08 · Vitor · ✅ vigente**\n\nCorpo um.", repr(e[0]["body"])
    assert e[1]["body"].endswith("Corpo dois."), repr(e[1]["body"])
    assert "lixo" not in e[0]["body"], "heading não-D- deve fechar a entrada"
    assert slugify("🔴 Não migrar — Railway mantida") == "nao-migrar-railway-mantida"
    assert _meta(e[0]["body"]) == ("02/08", "✅ vigente"), _meta(e[0]["body"])
    assert _meta(e[1]["body"]) == ("2026-08-18", "🔄 em"), _meta(e[1]["body"])
    print("selftest OK")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split", help="migração única do monólito")
    s.add_argument("--force", action="store_true", help="sobrescreve arquivos existentes")
    s.set_defaults(func=cmd_split)
    sub.add_parser("index", help="regera o índice").set_defaults(func=cmd_index)
    n = sub.add_parser("new", help="cria o próximo D- livre")
    n.add_argument("titulo")
    n.set_defaults(func=cmd_new)
    c = sub.add_parser("check", help="duplicidade de número e índice fresco")
    c.add_argument("--report-only", action="store_true")
    c.set_defaults(func=cmd_check)
    sub.add_parser("selftest", help="exercita o parser").set_defaults(func=cmd_selftest)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
