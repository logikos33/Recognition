"""Driver headless — Fase D3.

Executa o Claude Code (claude -p) numa tarefa fechada, ponta a ponta, sem copy-paste.

Fluxo:
  1. Lê spec de tarefa (markdown com front-matter YAML opcional).
  2. Monta prompt: árvore de arquivos + diff atual + constitution + spec.
  3. Chama `claude -p` em headless com allowedTools restritos.
  4. Roda EVAL definida pela spec (default | harness).
  5. Loop até max_retries reinjetando o erro pro modelo.
  6. Guard-rail: aborta se o diff tocar paths protegidos OU branch protegida.
  7. Verde + dentro do budget → commit + `gh pr create --base develop`. NUNCA merge.

Não usa --dangerously-skip-permissions; a allowlist é o trilho. Tudo loga em runs/<ts>.log.

Limites (L1): humano revisa o PR. Driver não toca main, não força push, não mergeia.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
DRIVER_DIR = Path(__file__).resolve().parent
RUNS_DIR = DRIVER_DIR / "runs"
CONFIG_PATH = DRIVER_DIR / "config.yaml"
CONSTITUTION_PATH = ROOT / "constitution.md"


# ---------------------------------------------------------------------------
# Logging — duplo: stdout (humano) + arquivo (auditoria do run)
# ---------------------------------------------------------------------------


def _setup_logging() -> tuple[logging.Logger, Path]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = RUNS_DIR / f"{ts}.log"
    logger = logging.getLogger("agent.driver")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger, log_path


# ---------------------------------------------------------------------------
# Config + spec
# ---------------------------------------------------------------------------


def _load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_spec(path: Path) -> tuple[dict[str, Any], str]:
    """Lê uma spec markdown com front-matter YAML opcional (delimitado por ---)."""
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            front = yaml.safe_load(raw[4:end]) or {}
            body = raw[end + 5 :]
            return front, body
    return {}, raw


# ---------------------------------------------------------------------------
# Contexto pro prompt
# ---------------------------------------------------------------------------


def _git(cmd: list[str]) -> str:
    out = subprocess.run(
        ["git", *cmd], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return out.stdout


def _build_prompt(spec_path: Path, spec_body: str, retry_feedback: str | None) -> str:
    """Monta o prompt injetando contexto factual (git) + constitution + spec."""
    files = _git(["ls-files"]).strip().splitlines()
    files_sample = "\n".join(files[:200])
    files_extra = f"\n... (+{len(files) - 200} arquivos)" if len(files) > 200 else ""
    diff = _git(["diff", "HEAD"]).strip() or "(sem alterações)"
    diff_trunc = diff[:8000]
    constitution = (
        CONSTITUTION_PATH.read_text(encoding="utf-8")
        if CONSTITUTION_PATH.exists()
        else "(constitution.md ausente)"
    )

    retry_block = ""
    if retry_feedback:
        retry_block = (
            "\n\n# Retry — última eval FALHOU. Corrija e tente de novo.\n\n"
            f"```\n{retry_feedback[:6000]}\n```\n"
        )

    return f"""Você é o executor headless do Recognition. Faça APENAS o que a spec pede.

# Regras inegociáveis (constitution C-01..C-08)

{constitution}

# Spec da tarefa ({spec_path.name})

{spec_body}

# Contexto do repo

## Arquivos rastreados (amostra)
```
{files_sample}{files_extra}
```

## Diff atual (vs HEAD)
```diff
{diff_trunc}
```
{retry_block}

# O que fazer

1. Implemente a mudança descrita na spec.
2. Rode a eval definida na spec; se falhar, corrija até passar.
3. NÃO faça commit, NÃO faça push, NÃO abra PR — o driver faz isso depois.
4. NÃO toque arquivos fora do escopo declarado na spec.

Se faltar contexto, leia os arquivos explicitamente em vez de adivinhar (princípio C-04)."""


# ---------------------------------------------------------------------------
# Chamada do claude -p
# ---------------------------------------------------------------------------


def _build_claude_cmd(prompt: str, model: str, allowed_tools: list[str]) -> list[str]:
    """Monta o comando do claude headless. Helper testável (sem subprocess)."""
    return [
        "claude",
        "-p",
        prompt,
        "--model",
        model,
        "--output-format",
        "json",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        ",".join(allowed_tools),
    ]


def _run_claude(
    prompt: str, model: str, allowed_tools: list[str], log: logging.Logger
) -> bool:
    """Chama claude headless. Retorna True se exit 0."""
    cmd = _build_claude_cmd(prompt, model, allowed_tools)
    log.info("Disparando claude -p (model=%s, tools=%d)", model, len(allowed_tools))
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log.info("claude exit=%d", result.returncode)
    if result.stderr.strip():
        log.warning("claude stderr: %s", result.stderr.strip()[:2000])
    try:
        payload = json.loads(result.stdout)
        log.info("claude resposta: %s", json.dumps(payload)[:2000])
    except json.JSONDecodeError:
        log.info("claude stdout (raw): %s", result.stdout[:2000])
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


def _eval_env() -> dict[str, str]:
    """Ambiente para subprocessos de eval: PATH com venv/bin no início.

    Garante que ruff, pytest, python etc. resolvem pro venv do repo sem exigir
    ativação manual do shell — problema que fez a eval do task-002 falhar.
    """
    import os

    venv_bin = str(ROOT / "venv" / "bin")
    path = os.environ.get("PATH", "")
    return {**os.environ, "PATH": f"{venv_bin}:{path}"}


def _run_eval(eval_name: str, config: dict[str, Any], log: logging.Logger) -> tuple[bool, str]:
    """Roda comandos da eval. Retorna (passou, output_combinado)."""
    commands = config["checks"].get(eval_name) or config["checks"]["default"]
    combined: list[str] = []
    env = _eval_env()
    for cmd in commands:
        log.info("EVAL: %s", cmd)
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, shell=True, env=env)
        head = f"\n$ {cmd}\n(exit {result.returncode})\n"
        combined.append(head + (result.stdout[-2000:] + result.stderr[-2000:]))
        if result.returncode != 0:
            log.error("EVAL FALHOU em: %s", cmd)
            return False, "".join(combined)
    return True, "".join(combined)


# ---------------------------------------------------------------------------
# Guard-rails
# ---------------------------------------------------------------------------


def _current_branch() -> str:
    return _git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()


def _changed_files() -> list[str]:
    out = _git(["status", "--porcelain"]).strip().splitlines()
    return [line[3:].strip() for line in out if line.strip()]


def _is_tree_dirty(porcelain_lines: list[str]) -> bool:
    """Retorna True se QUALQUER linha não-vazia existir no porcelain (modificada, staged ou untracked).

    Arquivos gitignored não aparecem no porcelain, portanto não activam este guard.
    Função pura — testável sem subprocess.
    """
    return any(line.strip() for line in porcelain_lines)


def _assert_clean_tree(log: logging.Logger) -> bool:
    """Working tree precisa estar TOTALMENTE limpa antes de criar a branch de trabalho.

    Untracked (??) também conta como sujo: se não forem comitados/stashados/gitignored,
    serão capturados pelo git add -A e entrarão no commit da tarefa, corrompendo o isolamento.
    Gitignored não aparecem no porcelain — não trippam este guard.
    """
    lines = _git(["status", "--porcelain"]).splitlines()
    if _is_tree_dirty(lines):
        dirty = [line for line in lines if line.strip()]
        log.error(
            "Working tree sujo — commit/stash/gitignore antes de rodar o driver.\n%s",
            "\n".join(dirty)[:2000],
        )
        return False
    return True


def _assert_base_branch(expected: str, log: logging.Logger) -> bool:
    """Driver tem que ser invocado da base (ex: develop). Garante reprodutibilidade do ponto de partida."""
    current = _current_branch()
    if current != expected:
        log.error(
            "Branch atual é '%s', mas o driver exige base '%s'. Rode `git checkout %s && git pull` antes.",
            current, expected, expected,
        )
        return False
    return True


def _make_work_branch_name(spec_path: Path) -> str:
    """Nome da branch de trabalho: agent/<stem-da-spec>-<timestampUTC>."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"agent/{spec_path.stem}-{ts}"


def _create_work_branch(name: str, log: logging.Logger) -> bool:
    """Cria e checa-out a branch de trabalho a partir do HEAD da base."""
    result = subprocess.run(
        ["git", "checkout", "-b", name], cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        log.error("Falha ao criar branch '%s': %s", name, result.stderr.strip())
        return False
    log.info("Branch de trabalho criada: %s", name)
    return True


def _check_guard_rails(config: dict[str, Any], log: logging.Logger) -> bool:
    branch = _current_branch()
    if branch in config["guard_rails"]["protected_branches"]:
        log.error("GUARD-RAIL: branch protegida (%s) — abortando push.", branch)
        return False
    protected = config["guard_rails"]["protected_paths"]
    for f in _changed_files():
        for prefix in protected:
            if f.startswith(prefix):
                log.error("GUARD-RAIL: arquivo protegido tocado (%s) — abortando push.", f)
                return False
    return True


# ---------------------------------------------------------------------------
# Commit + PR
# ---------------------------------------------------------------------------


def _parse_meta(spec_front: dict[str, Any], spec_body: str) -> dict[str, str]:
    """Extrai title/body do PR a partir do front-matter (com fallback pra heurística no body)."""
    title = spec_front.get("pr_title") or spec_front.get("title")
    if not title:
        m = re.search(r"^#\s+(.+)$", spec_body, re.MULTILINE)
        title = m.group(1).strip() if m else "Automated task"
    commit_msg = spec_front.get("commit_message") or f"feat: {title}"
    return {"title": title, "commit_message": commit_msg}


def _commit_and_pr(meta: dict[str, str], base_branch: str, log: logging.Logger) -> bool:
    branch = _current_branch()
    if branch == base_branch:
        log.error(
            "Recusa de commit: branch atual é a base '%s'. Driver deveria ter criado agent/* antes.",
            base_branch,
        )
        return False
    changed = _changed_files()
    if not changed:
        log.warning("Nada para commitar — claude não alterou arquivos.")
        return False
    subprocess.run(["git", "add", "--"] + changed, cwd=ROOT, check=True)
    diff_check = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT
    )
    if diff_check.returncode == 0:
        log.warning("Nada staged após git add — sem mudanças efetivas.")
        return False
    msg = meta["commit_message"] + "\n\nGenerated by agent-driver (D3). Reviewed manually before merge."
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "-u", "origin", branch], cwd=ROOT, check=True)
    pr = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base_branch,
            "--head",
            branch,
            "--title",
            meta["title"],
            "--body",
            f"Automated by agent-driver (D3). Human review required before merge.\n\nTask: {meta['title']}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    log.info("gh pr create stdout: %s", pr.stdout.strip())
    if pr.returncode != 0:
        log.error("gh pr create FALHOU: %s", pr.stderr.strip())
        return False
    return True


# ---------------------------------------------------------------------------
# Retry em memória — re-invoca implementador sem criar branch ou arquivo temp
# ---------------------------------------------------------------------------


def run_implementer_retry(
    spec_path: Path,
    spec_body: str,
    eval_name: str,
    review_feedback: str,
    config: dict[str, Any],
    log: logging.Logger,
) -> tuple[bool, str]:
    """Reinvoca o implementador com feedback do revisor em memória, na branch atual.

    NÃO cria branch, NÃO verifica clean tree, NÃO escreve arquivos temporários.
    Retorna (eval_passed, eval_output).
    """
    prompt = _build_prompt(spec_path, spec_body, review_feedback)
    if not _run_claude(prompt, config["model"], config["allowed_tools"], log):
        log.warning("claude saiu não-zero no retry pós-review; tentando eval mesmo assim.")
    return _run_eval(eval_name, config, log)


def commit_retry_on_branch(commit_msg: str, log: logging.Logger) -> bool:
    """Commit + push de changes pós-retry na branch atual (agent/*). Sem criar novo PR.

    Usa staging escopado (_changed_files) — não git add -A.
    """
    changed = _changed_files()
    if not changed:
        log.warning("commit_retry_on_branch: nada para commitar.")
        return False
    subprocess.run(["git", "add", "--"] + changed, cwd=ROOT, check=True)
    diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if diff_check.returncode == 0:
        log.warning("commit_retry_on_branch: nada staged.")
        return False
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT, check=True)
    branch = _current_branch()
    result = subprocess.run(
        ["git", "push", "origin", branch],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        log.error("Push falhou após retry: %s", result.stderr.strip())
        return False
    log.info("Retry commitado e enviado para branch %s.", branch)
    return True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Driver headless do Claude Code (D3).")
    parser.add_argument("spec", type=Path, help="Caminho da spec de tarefa (.md)")
    parser.add_argument("--dry-run", action="store_true", help="Não abre PR — só roda claude + eval.")
    args = parser.parse_args()

    log, log_path = _setup_logging()
    log.info("=== agent-driver D3 ===")
    log.info("Spec: %s", args.spec)
    log.info("Log: %s", log_path)

    if not args.spec.exists():
        log.error("Spec não encontrada: %s", args.spec)
        return 2

    config = _load_config()
    spec_front, spec_body = _load_spec(args.spec)
    eval_name = spec_front.get("eval", "default")
    base_branch = config.get("base_branch", "develop")
    model = config["model"]
    # Spec pode sobrescrever budget_minutes (tarefas complexas precisam de mais tempo)
    budget_minutes = int(spec_front.get("budget_minutes", config["budget_minutes"]))

    # Isolamento: tree limpa + branch base correta + criar agent/<task>-<ts>
    if not _assert_clean_tree(log):
        return 7
    if not _assert_base_branch(base_branch, log):
        return 8
    work_branch = _make_work_branch_name(args.spec)
    if not _create_work_branch(work_branch, log):
        return 9

    deadline = time.monotonic() + budget_minutes * 60
    log.info("Budget: %d min (config=%d, spec=%s)", budget_minutes, config["budget_minutes"],
             spec_front.get("budget_minutes", "não definido"))
    feedback: str | None = None

    for attempt in range(1, config["max_retries"] + 1):
        if time.monotonic() > deadline:
            log.error("Budget de %d min estourado — abortando.", budget_minutes)
            return 3

        log.info("=== Tentativa %d/%d ===", attempt, config["max_retries"])
        prompt = _build_prompt(args.spec, spec_body, feedback)
        if not _run_claude(prompt, model, config["allowed_tools"], log):
            log.warning("claude saiu não-zero; mesmo assim tentando eval (pode ter feito edits).")

        passed, output = _run_eval(eval_name, config, log)
        if passed:
            log.info("EVAL VERDE na tentativa %d.", attempt)
            break
        feedback = output
    else:
        log.error("EVAL não passou em %d tentativas — abortando.", config["max_retries"])
        return 4

    if not _check_guard_rails(config, log):
        return 5

    if args.dry_run:
        log.info("--dry-run: pulando commit/PR. Diff disponível em git status.")
        return 0

    meta = _parse_meta(spec_front, spec_body)
    if not _commit_and_pr(meta, base_branch, log):
        return 6

    log.info("=== PR aberto. Humano revisa. NUNCA auto-merge. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
