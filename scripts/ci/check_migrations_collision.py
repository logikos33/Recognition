"""
Guard-rail: torna impossível a colisão de numeração de migration
(infra/migrations/NNN_*.sql) entre PRs abertos em paralelo.

Contexto: colisão de numeração já derrubou o startup da API uma vez (ADR-0021)
e quase se repetiu ontem — PR #279 e PR #281 chegaram a criar, em worktrees
paralelas, dois arquivos com o mesmo prefixo "108_*.sql"; só não colidiu de
verdade porque um dos dois foi renumerado a tempo, por sorte, não por CI.
`scripts/ci/check_migrations_hygiene.py` já pega duplicata dentro da árvore
que foi feito checkout — mas só enxerga o que já está mergeado na base; não
enxerga OUTRO PR aberto que ainda não foi mergeado. Este script cobre esse
buraco.

Dois checks, sempre para as migrations ADICIONADAS neste PR (diff contra o
merge-base com a branch base — nunca HEAD~1, que não tem relação nenhuma com
"o que este PR de fato adiciona" quando há mais de um commit ou quando a base
avançou):

  1. DETERMINÍSTICO, sempre roda, nunca falha por instabilidade externa:
     o prefixo NNN de cada migration nova não pode colidir com (a) outra
     migration nova NO MESMO PR nem (b) uma migration que já existe em
     origin/<base-ref>.

  2. BEST-EFFORT, via GitHub API (`gh api`, autenticado pelo GITHUB_TOKEN
     padrão do Actions — precisa de `permissions: pull-requests: read` no
     job): o mesmo prefixo não pode já ter sido adicionado por OUTRO pull
     request aberto contra a mesma branch base. Qualquer falha em FALAR com a
     API (gh ausente, sem rede, rate limit, repo não resolvido) vira um
     WARNING impresso no log e NÃO derruba o build — só uma colisão
     CONFIRMADA (resposta da API obtida com sucesso e prefixo batendo) falha
     o check. Isso é uma escolha deliberada: preferimos um falso-negativo
     ocasional (API fora do ar) a um CI vermelho por instabilidade de rede
     num check que é, por natureza, best-effort.

Uso em CI (ver .github/workflows/ci.yml, job migrations-collision-guard):
  python scripts/ci/check_migrations_collision.py \
      --base-ref "$GITHUB_BASE_REF" --pr-number "$PR_NUMBER"

Uso local (dry-run manual, ex.: reproduzir uma colisão forjada):
  git add infra/migrations/108_teste_colisao.sql   # arquivo forjado, NÃO commitado
  python scripts/ci/check_migrations_collision.py --base-ref develop
  git reset infra/migrations/108_teste_colisao.sql && rm infra/migrations/108_teste_colisao.sql
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MIGRATIONS_PATHSPEC = "infra/migrations"
MIGRATIONS_PREFIX = "infra/migrations/"
FILENAME_RE = re.compile(r"^(\d+)_.+\.sql$")

GH_TIMEOUT_SECONDS = 30


class GitError(RuntimeError):
    """Falha ao rodar um comando git — sempre fatal (check 1 é determinístico)."""


class RemoteCheckUnavailable(RuntimeError):
    """Falha ao falar com a API do GitHub — sempre vira WARNING, nunca fatal."""


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def _prefix_of(filename: str) -> str | None:
    match = FILENAME_RE.match(pathlib.Path(filename).name)
    return match.group(1) if match else None


def resolve_merge_base(base_ref: str) -> str:
    """merge-base entre origin/<base_ref> e o estado atual (HEAD + staged).

    É o mesmo conjunto de commits que o diff de um PR no GitHub mostra — por
    isso usamos merge-base, e não HEAD~1 (que só faz sentido se o PR tiver
    exatamente 1 commit e a base nunca tiver avançado)."""
    try:
        _run_git(["rev-parse", "--verify", f"origin/{base_ref}"])
    except GitError:
        _run_git(["fetch", "origin", base_ref])
    return _run_git(["merge-base", f"origin/{base_ref}", "HEAD"]).strip()


def added_migrations_in_diff(merge_base: str) -> dict[str, list[str]]:
    """Prefixo -> lista de filenames ADICIONADOS entre merge_base e o estado
    atual do working tree.

    Comparar contra o working tree (não contra HEAD) é deliberado: em CI, o
    checkout do PR já está tudo commitado, então não muda nada; localmente,
    permite testar uma migration forjada só com `git add`, sem precisar
    commitar (git diff <treeish> sem --cached inclui staged + committed)."""
    out = _run_git(
        [
            "diff",
            "--name-status",
            "--diff-filter=A",
            merge_base,
            "--",
            MIGRATIONS_PATHSPEC,
        ]
    )
    added: dict[str, list[str]] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        status, _, filename = line.partition("\t")
        if status != "A":
            continue
        prefix = _prefix_of(filename)
        if prefix is None:
            continue
        added.setdefault(prefix, []).append(filename)
    return added


def base_migrations(base_ref: str) -> dict[str, str]:
    """Prefixo -> filename das migrations que já existem em origin/<base_ref>."""
    out = _run_git(
        ["ls-tree", "-r", "--name-only", f"origin/{base_ref}", "--", MIGRATIONS_PATHSPEC]
    )
    base_map: dict[str, str] = {}
    for filename in out.splitlines():
        prefix = _prefix_of(filename)
        if prefix is None:
            continue
        base_map.setdefault(prefix, filename)
    return base_map


def check_within_pr_duplicates(added: dict[str, list[str]]) -> list[str]:
    errors = []
    for prefix, filenames in sorted(added.items()):
        if len(filenames) > 1:
            errors.append(
                f"prefixo '{prefix}' usado por mais de um arquivo NESTE MESMO PR: "
                f"{', '.join(sorted(filenames))}. Renumere um deles."
            )
    return errors


def check_against_base(added: dict[str, list[str]], base_ref: str, base_map: dict[str, str]) -> list[str]:
    errors = []
    for prefix, filenames in sorted(added.items()):
        base_filename = base_map.get(prefix)
        if base_filename is None:
            continue
        for filename in filenames:
            errors.append(
                f"{filename}: prefixo '{prefix}' já existe em origin/{base_ref} "
                f"({base_filename}). Escolha o próximo prefixo livre "
                f"(`ls infra/migrations/*.sql | sort | tail -1`)."
            )
    return errors


def _gh_jsonl(args: list[str]) -> list[dict]:
    """Roda `gh <args>` e parseia stdout como JSON Lines (um objeto por
    linha — obtido com `--jq '.[] | ... | tojson'` nas chamadas abaixo, a
    forma que sobrevive à paginação do `gh api --paginate` sem virar vários
    arrays JSON concatenados e inválidos)."""
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RemoteCheckUnavailable("gh CLI não encontrado no PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RemoteCheckUnavailable(f"gh {' '.join(args)} expirou (timeout)") from exc
    if result.returncode != 0:
        raise RemoteCheckUnavailable(
            (result.stderr or result.stdout).strip() or f"gh saiu com código {result.returncode}"
        )
    items = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def _resolve_repo(explicit: str | None) -> str:
    if explicit:
        return explicit
    items = _gh_jsonl(["repo", "view", "--json", "nameWithOwner", "--jq", ". | tojson"])
    if not items:
        raise RemoteCheckUnavailable("gh repo view não retornou nameWithOwner")
    return items[0]["nameWithOwner"]


def check_open_prs(
    base_ref: str, pr_number: int | None, repo: str | None, added: dict[str, list[str]]
) -> tuple[list[str], int]:
    """Best-effort: colisões contra migrations adicionadas por OUTRO PR aberto
    contra a mesma base. Levanta RemoteCheckUnavailable (nunca falha o build
    sozinha) se a API não puder ser consultada com confiança."""
    resolved_repo = _resolve_repo(repo)

    open_prs = _gh_jsonl(
        [
            "api",
            "-X",
            "GET",
            f"repos/{resolved_repo}/pulls",
            "-f",
            "state=open",
            "-f",
            f"base={base_ref}",
            "--paginate",
            "--jq",
            ".[] | {number} | tojson",
        ]
    )
    other_pr_numbers = [pr["number"] for pr in open_prs if pr["number"] != pr_number]

    collisions: list[str] = []
    for other_pr_number in other_pr_numbers:
        files = _gh_jsonl(
            [
                "api",
                "-X",
                "GET",
                f"repos/{resolved_repo}/pulls/{other_pr_number}/files",
                "--paginate",
                "--jq",
                ".[] | {filename, status} | tojson",
            ]
        )
        for f in files:
            if f.get("status") != "added":
                continue
            filename = f.get("filename", "")
            if not filename.startswith(MIGRATIONS_PREFIX):
                continue
            prefix = _prefix_of(filename)
            if prefix is None or prefix not in added:
                continue
            for local_filename in added[prefix]:
                collisions.append(
                    f"{local_filename}: prefixo '{prefix}' já foi adicionado pelo PR "
                    f"aberto #{other_pr_number} ({filename}). Escolha o próximo prefixo "
                    f"livre antes de atualizar este PR."
                )
    return collisions, len(other_pr_numbers)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("GITHUB_BASE_REF") or "develop",
        help="branch base do PR (default: $GITHUB_BASE_REF ou 'develop')",
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        default=(int(os.environ["PR_NUMBER"]) if os.environ.get("PR_NUMBER") else None),
        help="número deste PR, para se auto-excluir do check contra outros PRs abertos",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="owner/repo (default: $GITHUB_REPOSITORY, senão resolvido via `gh repo view`)",
    )
    parser.add_argument(
        "--skip-remote-check",
        action="store_true",
        help="pula o check best-effort contra outros PRs abertos (só roda o check 1, determinístico)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        merge_base = resolve_merge_base(args.base_ref)
    except GitError as exc:
        print(f"::error::Não foi possível calcular o merge-base com origin/{args.base_ref}: {exc}")
        return 1

    added = added_migrations_in_diff(merge_base)

    if not added:
        print(
            f"Nenhuma migration nova em infra/migrations/ neste PR "
            f"(merge-base {merge_base[:12]} com origin/{args.base_ref}) — nada para checar."
        )
        return 0

    print(f"Migrations novas neste PR (merge-base {merge_base[:12]} com origin/{args.base_ref}):")
    for prefix, filenames in sorted(added.items()):
        for filename in filenames:
            print(f"  - {filename} (prefixo '{prefix}')")

    errors = check_within_pr_duplicates(added)

    try:
        base_map = base_migrations(args.base_ref)
    except GitError as exc:
        print(f"::error::Não foi possível listar infra/migrations/ em origin/{args.base_ref}: {exc}")
        return 1
    errors += check_against_base(added, args.base_ref, base_map)

    warnings: list[str] = []
    if args.skip_remote_check:
        warnings.append("Check contra outros PRs abertos PULADO (--skip-remote-check).")
    else:
        try:
            collisions, checked_count = check_open_prs(args.base_ref, args.pr_number, args.repo, added)
        except RemoteCheckUnavailable as exc:
            warnings.append(
                f"Check contra outros PRs abertos indisponível (best-effort, NÃO falha o build): {exc}"
            )
        else:
            errors += collisions
            print(
                f"\nChecados {checked_count} PR(s) aberto(s) contra origin/{args.base_ref} "
                f"via GitHub API (best-effort)."
            )

    if warnings:
        print("\nAVISOS (não falham o build):")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print("\nGuard-rail de colisão de migrations FALHOU:\n")
        for e in errors:
            print(f"  - {e}\n")
        return 1

    print("\nGuard-rail de colisão de migrations OK — nenhuma colisão de numeração encontrada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
