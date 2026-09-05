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

  2. Migration NOVA que apaga dado ou reescreve credencial (issues #683/#694).
     A guarda de redeploy (infra/migrations/runner_core.py) impede que uma
     migration com DROP TABLE / DROP COLUMN / DELETE FROM / TRUNCATE ou com
     atribuição a `password_hash` rode num banco que já tem tenant — foi assim
     que a 049 apagava o histórico de contagem e a 027/040 devolviam a senha do
     superadmin ao hash do git a cada deploy. Consequência: uma migration NOVA
     escrita com esses comandos simplesmente NÃO RODA em produção. Este check
     usa o MESMO detector do runner (runner_core.destructive_reason — fonte
     única, não regex duplicada) e falha em CI, antes do merge, para qualquer
     arquivo fora de infra/migrations/.destructive-baseline (a dívida histórica
     já aplicada, que deve encolher e nunca crescer).

  3. Diretório migrations/ na raiz do repositório, além de infra/migrations/.
     O projeto usa infra/migrations/ como fonte única (ADR-0010); um segundo
     diretório de migrations já existiu no histórico do repo e foi removido
     (PRs #214/#215) — este check é a garantia de não-regressão.

Uso:
  python scripts/ci/check_migrations_hygiene.py

Testes: services/api/tests/unit/ci/test_migrations_hygiene_gate.py — cada check
recebe a RAIZ de propósito, para que o teste possa montar um repositório
forjado (prefixo duplicado novo, migration com DROP, diretório legado) e provar
que o gate REPROVA. Rodar o gate só contra o repositório saudável prova que ele
existe, não que ele morde.
"""

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# Só para achar runner_core; os caminhos de dado saem de _dir_migrations(raiz).
MIGRATIONS_DIR = REPO_ROOT / "infra" / "migrations"

PREFIX_RE = re.compile(r"^(\d+)_.+\.sql$")


def _dir_migrations(raiz: pathlib.Path) -> pathlib.Path:
    return raiz / "infra" / "migrations"


def _rel(caminho: pathlib.Path, raiz: pathlib.Path) -> str:
    """Caminho relativo à raiz; nome puro quando a raiz é forjada (teste)."""
    try:
        return caminho.relative_to(raiz).as_posix()
    except ValueError:
        return caminho.name


def _load_baseline(raiz: pathlib.Path = REPO_ROOT) -> set[str]:
    """Lê os PREFIXOS duplicados aceitos (mesma semântica de
    runner_core._load_baseline_duplicate_versions: uma versão por linha,
    ex.: "052"). Comentários com '#' e linhas vazias ignorados."""
    arquivo = _dir_migrations(raiz) / ".duplicate-prefix-baseline"
    if not arquivo.exists():
        return set()
    entries: set[str] = set()
    for raw_line in arquivo.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entries.add(line)
    return entries


def check_duplicate_prefixes(raiz: pathlib.Path = REPO_ROOT) -> list[str]:
    """Retorna mensagens de erro para prefixos NNN duplicados fora da baseline."""
    dir_migrations = _dir_migrations(raiz)
    if not dir_migrations.is_dir():
        return [f"Diretório {_rel(dir_migrations, raiz)}/ não encontrado."]

    baseline = _load_baseline(raiz)

    by_prefix: dict[str, list[str]] = {}
    for f in sorted(dir_migrations.glob("*.sql")):
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


def _entradas_de_baseline(arquivo: pathlib.Path) -> set[str]:
    """Uma entrada por linha; '#' comenta, linhas vazias ignoradas."""
    if not arquivo.exists():
        return set()
    return {
        linha.strip()
        for linha in arquivo.read_text().splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    }


def check_no_new_destructive_migration(raiz: pathlib.Path = REPO_ROOT) -> list[str]:
    """Migration nova que apaga dado ou reescreve credencial => vermelho."""
    # runner_core vem SEMPRE do repositório real, mesmo com raiz forjada: o
    # detector é fonte única com o runner de produção — um dublê aqui testaria
    # o dublê, não o gate.
    sys.path.insert(0, str(MIGRATIONS_DIR))
    import runner_core  # infra/migrations/runner_core.py — mesmo detector do runner

    dir_migrations = _dir_migrations(raiz)
    arquivo_baseline = dir_migrations / ".destructive-baseline"
    conhecidas = _entradas_de_baseline(arquivo_baseline)
    erros: list[str] = []
    for f in sorted(dir_migrations.glob("*.sql")):
        if f.name in conhecidas:
            continue
        motivo = runner_core.destructive_reason(f.read_text(encoding="utf-8"))
        if motivo is None:
            continue
        erros.append(
            f"{f.name} {motivo}. Migrations são forward-only (CLAUDE.md: nunca "
            f"DROP / DELETE FROM / TRUNCATE) e, pior, a guarda de redeploy do "
            f"runner PULA esse arquivo em qualquer banco que já tenha tenant — "
            f"ou seja, ele não rodaria em produção (issues #683/#694). Reescreva "
            f"a migration sem o comando destrutivo. NÃO adicione o arquivo a "
            f"{_rel(arquivo_baseline, raiz)}: aquela lista é "
            f"dívida histórica já aplicada e só encolhe."
        )
    return erros


def check_baseline_destrutiva_nao_tem_fantasma(raiz: pathlib.Path = REPO_ROOT) -> list[str]:
    """Entrada de baseline sem arquivo correspondente => a lista não encolheu sozinha."""
    dir_migrations = _dir_migrations(raiz)
    arquivo_baseline = dir_migrations / ".destructive-baseline"
    existentes = {f.name for f in dir_migrations.glob("*.sql")}
    fantasmas = sorted(_entradas_de_baseline(arquivo_baseline) - existentes)
    if fantasmas:
        return [
            f"{_rel(arquivo_baseline, raiz)} lista arquivo(s) "
            f"que não existem mais: {', '.join(fantasmas)}. Remova a(s) linha(s)."
        ]
    return []


def check_no_duplicate_migrations_dir(raiz: pathlib.Path = REPO_ROOT) -> list[str]:
    """Retorna erro se existir um segundo diretório migrations/ na raiz do repo."""
    legado = raiz / "migrations"
    if legado.exists():
        return [
            f"Diretório legado {_rel(legado, raiz)}/ existe "
            f"além de infra/migrations/. A fonte única de migrations é infra/migrations/ "
            f"(ADR-0010) — um segundo diretório é exatamente o tipo de duplicação que já "
            f"causou incidentes de numeração (ADR-0021). Remova o diretório legado ou mova "
            f"o conteúdo para infra/migrations/."
        ]
    return []


def checar(raiz: pathlib.Path = REPO_ROOT) -> list[str]:
    """Todos os checks de higiene, na raiz dada."""
    return (
        check_duplicate_prefixes(raiz)
        + check_no_new_destructive_migration(raiz)
        + check_baseline_destrutiva_nao_tem_fantasma(raiz)
        + check_no_duplicate_migrations_dir(raiz)
    )


def main() -> int:
    errors = checar(REPO_ROOT)

    if errors:
        print("Guard-rail de higiene de migrations FALHOU:\n")
        for e in errors:
            print(f"  - {e}\n")
        return 1

    print(
        "Guard-rail de higiene de migrations OK (sem duplicata de prefixo nova, "
        "sem migration destrutiva nova, sem diretório de migrations duplicado)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
