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


def _run_claude(prompt: str, allowed_tools: list[str], log: logging.Logger) -> bool:
    """Chama claude headless. Retorna True se exit 0."""
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        ",".join(allowed_tools),
    ]
    log.info("Disparando claude -p (tools=%d)", len(allowed_tools))
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


def _run_eval(eval_name: str, config: dict[str, Any], log: logging.Logger) -> tuple[bool, str]:
    """Roda comandos da eval. Retorna (passou, output_combinado)."""
    commands = config["checks"].get(eval_name) or config["checks"]["default"]
    combined: list[str] = []
    for cmd in commands:
        log.info("EVAL: %s", cmd)
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, shell=True)
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


def _commit_and_pr(meta: dict[str, str], log: logging.Logger) -> bool:
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    diff_check = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT
    )
    if diff_check.returncode == 0:
        log.warning("Nada para commitar — claude não alterou arquivos.")
        return False
    msg = meta["commit_message"] + "\n\nGenerated by agent-driver (D3). Reviewed manually before merge."
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    branch = _current_branch()
    subprocess.run(["git", "push", "-u", "origin", branch], cwd=ROOT, check=True)
    pr = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            "develop",
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

    deadline = time.monotonic() + config["budget_minutes"] * 60
    feedback: str | None = None

    for attempt in range(1, config["max_retries"] + 1):
        if time.monotonic() > deadline:
            log.error("Budget de %d min estourado — abortando.", config["budget_minutes"])
            return 3

        log.info("=== Tentativa %d/%d ===", attempt, config["max_retries"])
        prompt = _build_prompt(args.spec, spec_body, feedback)
        if not _run_claude(prompt, config["allowed_tools"], log):
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
    if not _commit_and_pr(meta, log):
        return 6

    log.info("=== PR aberto. Humano revisa. NUNCA auto-merge. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
