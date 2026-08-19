"""
Guard-rail de higiene dos workflows do GitHub Actions.

Dois checks, ambos motivados por defeito REAL e medido — não por hipótese.

  1. CHAVE DUPLICADA num mapa YAML.
     O GitHub rejeita o arquivo inteiro na validação: o run nasce `failure`
     com ZERO jobs, ZERO log e ZERO tempo faturado. Não parece defeito de
     workflow — parece "a segurança rodou e reprovou".

     Medido: o commit 6f895b0 (18/08 13:01 UTC) deixou `working-directory`
     repetido duas vezes no mesmo step do `npm audit`. A partir dali o
     `security-scan.yml` NUNCA MAIS executou — 85 runs seguidos em `failure`,
     e com ele foram junto gitleaks, bandit, pip-audit, npm audit e SBOM.
     Última execução de verdade: 18/08 13:06 UTC.

     ⚠️ `yaml.safe_load` do Python NÃO reclama de chave duplicada: fica
     silenciosamente com a última. Por isso "o YAML parseia" não prova nada, e
     por isso este check usa um loader próprio.

  2. Job sem `timeout-minutes`.
     O default do GitHub é 360 minutos. Um passo pendurado não falha — queima
     seis horas de runner enquanto o quadro de checks fica amarelo.

     Medido no job `Frontend tests` (#465):
         run 32168166726  Install Playwright browsers  17:56 -> 23:55  (6h)
         run 32165120756  Install Playwright browsers  17:21 -> 17:55  (34min)
     Nos dois o passo de E2E ficou `skipped` — o teste nunca foi o culpado.

Uso:
  python scripts/ci/check_workflow_hygiene.py
"""

import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Teto de sanidade: timeout acima disso não protege de nada — o ponto é falhar
# rápido e visível, não adiar a descoberta.
MAX_MINUTES = 60


class _DuplicateKeyError(Exception):
    pass


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader que RECUSA chave duplicada, como o GitHub faz."""


def _no_duplicates(loader: _StrictLoader, node, deep: bool = False):
    seen: set = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            mark = key_node.start_mark
            raise _DuplicateKeyError(f"chave `{key}` repetida na linha {mark.line + 1}")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates
)


def main() -> int:
    if not WORKFLOWS_DIR.is_dir():
        print(f"Diretório de workflows não encontrado: {WORKFLOWS_DIR}")
        return 1

    errors: list[str] = []
    jobs_checked = 0
    files_checked = 0

    paths = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
    if not paths:
        print(f"Nenhum workflow encontrado em {WORKFLOWS_DIR}")
        return 1

    for path in paths:
        rel = path.relative_to(REPO_ROOT)
        files_checked += 1
        try:
            doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_StrictLoader)
        except _DuplicateKeyError as exc:
            errors.append(
                f"{rel}: {exc} — o GitHub rejeita o arquivo INTEIRO "
                f"(run `failure` com zero jobs e zero log)"
            )
            continue
        except yaml.YAMLError as exc:
            errors.append(f"{rel}: YAML inválido: {exc}")
            continue

        if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
            errors.append(f"{rel}: sem bloco `jobs` utilizável")
            continue

        for job_id, job in doc["jobs"].items():
            if not isinstance(job, dict) or "uses" in job:
                # job de workflow reutilizável herda o timeout de lá
                continue
            jobs_checked += 1
            timeout = job.get("timeout-minutes")
            if timeout is None:
                errors.append(
                    f"{rel}: job `{job_id}` sem `timeout-minutes` — "
                    f"o default do GitHub é 360min (6h de runner por travada)"
                )
            elif not isinstance(timeout, int) or timeout <= 0:
                errors.append(
                    f"{rel}: job `{job_id}` com `timeout-minutes` inválido: {timeout!r}"
                )
            elif timeout > MAX_MINUTES:
                errors.append(
                    f"{rel}: job `{job_id}` pede {timeout}min (teto: {MAX_MINUTES}min)"
                )

    if errors:
        print("Guard-rail de higiene de workflows FALHOU:\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"Guard-rail de higiene de workflows OK "
        f"({files_checked} arquivos, {jobs_checked} jobs: sem chave duplicada, "
        f"todos com timeout-minutes)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
