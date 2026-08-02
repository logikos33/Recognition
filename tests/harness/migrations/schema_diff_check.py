"""
Check de idempotência em profundidade (C-02): compara o schema resultante da
passada 1 vs passada 2 do runner, tolerando APENAS a divergência histórica já
registrada em .schema-diff-baseline (dívida das migrations 011/049 — em triagem
humana, ver README.md deste diretório).

Semântica (mesmo padrão do .duplicate-prefix-baseline do check de prefixo):
  - diff vazio                          → verde (dívida resolvida — encolha a baseline!)
  - diff ⊆ baseline                     → verde (só dívida conhecida)
  - qualquer linha NOVA fora da baseline → vermelho, imprime só o delta novo

A comparação usa "linhas materiais" do diff unificado, não o texto bruto do
diff: linhas +/- com conteúdo real (ignora vazias e comentários SQL "--", que
são formatação do pg_dump, não schema — e cuja remoção viraria "---" no diff,
colidindo com o cabeçalho de arquivo). Isso torna a baseline estável a
deslocamentos de hunk/contexto quando migrations não relacionadas mudam a
vizinhança no dump.

Contagem por multiconjunto (Counter), não set: se a MESMA linha de dívida
aparecer mais vezes que na baseline (ex.: outra tabela ganhando uma coluna
homônima só na 2ª passada), a ocorrência excedente é delta novo → vermelho.

Uso:
  python tests/harness/migrations/schema_diff_check.py PASS1_DUMP PASS2_DUMP
  python tests/harness/migrations/schema_diff_check.py PASS1_DUMP PASS2_DUMP --print-material
      (imprime as linhas materiais do diff atual — insumo para ENCOLHER a
       baseline manualmente quando parte da dívida for resolvida)
"""

import argparse
import difflib
import pathlib
import sys
from collections import Counter

BASELINE_DEFAULT = pathlib.Path(__file__).resolve().parent / ".schema-diff-baseline"


def material_diff_lines(pass1_path: pathlib.Path, pass2_path: pathlib.Path) -> Counter:
    """Linhas +/- de conteúdo real do diff unificado entre os dois dumps.

    n=0 (zero contexto): só linhas efetivamente mudadas entram no diff.
    Cabeçalhos ---/+++ são as duas PRIMEIRAS linhas do unified_diff — pulados
    por posição, não por prefixo: um comentário SQL removido ("-- Name: ...")
    vira "--- Name: ..." no diff e um filtro por prefixo o confundiria com
    cabeçalho. Comentários SQL e linhas vazias são filtrados dos dois lados
    (formatação do pg_dump, não schema).
    """
    a = pass1_path.read_text().splitlines()
    b = pass2_path.read_text().splitlines()
    lines: Counter = Counter()
    for i, raw in enumerate(difflib.unified_diff(a, b, lineterm="", n=0)):
        if i < 2 or raw.startswith("@@") or not raw:
            continue
        marker, content = raw[0], raw[1:].rstrip()
        if marker not in "+-":
            continue
        if not content.strip() or content.lstrip().startswith("--"):
            continue
        lines[f"{marker}{content}"] += 1
    return lines


def load_baseline(path: pathlib.Path) -> Counter:
    """Baseline: uma linha material por linha do arquivo; '#' comenta; vazias ignoradas."""
    baseline: Counter = Counter()
    if not path.exists():
        return baseline
    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        baseline[line] += 1
    return baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff de schema passada 1 vs 2 com baseline")
    parser.add_argument("pass1", type=pathlib.Path, help="dump normalizado da passada 1")
    parser.add_argument("pass2", type=pathlib.Path, help="dump normalizado da passada 2")
    parser.add_argument(
        "--baseline", type=pathlib.Path, default=BASELINE_DEFAULT,
        help=f"arquivo de baseline (default: {BASELINE_DEFAULT})",
    )
    parser.add_argument(
        "--print-material", action="store_true",
        help="imprime as linhas materiais do diff atual e sai (para manutenção da baseline)",
    )
    args = parser.parse_args()

    diff = material_diff_lines(args.pass1, args.pass2)

    if args.print_material:
        for line, count in sorted(diff.items()):
            for _ in range(count):
                print(line)
        return 0

    baseline = load_baseline(args.baseline)
    new_lines = diff - baseline       # excedente fora da dívida conhecida
    resolved = baseline - diff        # dívida que sumiu — baseline pode encolher

    if not diff:
        print("Schema idêntico entre passada 1 e passada 2 (diff vazio).")
        if baseline:
            print(
                f"NOTA: a baseline ({args.baseline}) ainda lista {sum(baseline.values())} "
                "linha(s) de dívida que não ocorrem mais — remova o arquivo (dívida quitada)."
            )
        return 0

    if new_lines:
        print("Schema divergiu entre passada 1 e passada 2 com delta NOVO fora da baseline (viola C-02):\n")
        for line, count in sorted(new_lines.items()):
            suffix = f"  (x{count})" if count > 1 else ""
            print(f"  {line}{suffix}")
        print(
            f"\n{sum(new_lines.values())} linha(s) nova(s). A baseline "
            f"({args.baseline}) cobre só a dívida histórica 011/049 e deve ENCOLHER, "
            "nunca crescer — corrija a migration nova (idempotência de verdade: mesma "
            "passada, mesmo schema), não adicione à baseline."
        )
        return 1

    print(
        f"Divergência passada 1 vs 2 é exatamente a dívida conhecida da baseline "
        f"({sum(diff.values())} linha(s), migrations 011/049 — em triagem). Verde."
    )
    if resolved:
        print(
            f"NOTA: {sum(resolved.values())} linha(s) da baseline não ocorrem mais — "
            "encolha a baseline removendo-as:"
        )
        for line, count in sorted(resolved.items()):
            suffix = f"  (x{count})" if count > 1 else ""
            print(f"  {line}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
