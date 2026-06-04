"""Queue runner — Fase L2.

Executa uma lista ordenada de specs sequencialmente. Auto-mergeia SOMENTE tarefas
com risk: low, CI verde e base = develop. Tarefas risk: security PARAM para revisão
humana.

Princípios de segurança (inegociáveis):
  - Spec SEM campo `risk` → tratada como `security` (fail-safe).
  - Auto-merge somente: risk == "low" AND checks = success AND base == "develop".
  - NUNCA auto-mergeia em main ou staging.
  - NUNCA --admin, NUNCA bypass de checks, NUNCA force-merge.
  - Revisor adversarial (Opus) avalía todo PR antes do merge (task-008).
  - Safeguard paths: qualquer toque → ESCALATE, sem auto-merge.
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DRIVER_DIR = Path(__file__).resolve().parent
ROOT = DRIVER_DIR.parent.parent
RUNS_DIR = DRIVER_DIR / "runs"
CONFIG_PATH = DRIVER_DIR / "config.yaml"

# Garante que DRIVER_DIR está no sys.path para imports locais (reviewer.py)
if str(DRIVER_DIR) not in sys.path:
    sys.path.insert(0, str(DRIVER_DIR))

from reviewer import _get_pr_changed_files, run_review  # noqa: E402

# Exit codes
EXIT_OK = 0
EXIT_PAUSED_SECURITY = 1    # task security detectada — pausado para revisão humana
EXIT_CI_FAILED = 2          # CI falhou numa task low-risk — pausado
EXIT_DRIVER_FAILED = 3      # driver falhou para uma spec
EXIT_NO_QUEUE = 4           # nenhuma spec fornecida e queue.txt ausente
EXIT_REVIEWER_ESCALATED = 5  # revisor escalou — PR aberto para revisão humana


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _setup_logging(label: str = "queue") -> tuple[logging.Logger, Path]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = RUNS_DIR / f"{label}-{ts}.log"
    logger = logging.getLogger("agent.queue_runner")
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


def _load_front_matter(path: Path) -> dict[str, Any]:
    """Lê apenas o front-matter YAML de uma spec markdown."""
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            return yaml.safe_load(raw[4:end]) or {}
    return {}


# ---------------------------------------------------------------------------
# Risk parsing — pura, testável, sem efeitos colaterais
# ---------------------------------------------------------------------------


def _parse_risk(front: dict[str, Any]) -> str:
    """Extrai risk do front-matter. Default = 'security' (fail-safe).

    Ausência do campo `risk` é tratada como 'security'.
    Qualquer valor desconhecido também cai em 'security'.
    """
    value = front.get("risk", "security")
    if value not in ("low", "security"):
        return "security"
    return str(value)


# ---------------------------------------------------------------------------
# Decisão de merge — pura, testável, sem efeitos colaterais
# ---------------------------------------------------------------------------


def _should_auto_merge(risk: str, checks_passed: bool, base_branch: str) -> bool:
    """Retorna True SOMENTE se: risk == 'low' AND checks_passed AND base == 'develop'.

    NUNCA retorna True para main, staging ou qualquer base != 'develop'.
    NUNCA retorna True para risk != 'low'.
    """
    return risk == "low" and checks_passed and base_branch == "develop"


# ---------------------------------------------------------------------------
# Parse do número de PR a partir do output do driver
# ---------------------------------------------------------------------------


def _parse_pr_number(output: str) -> str | None:
    """Extrai o número do PR do output do driver (URL gerada por gh pr create)."""
    m = re.search(r"/pull/(\d+)", output)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Decisão do revisor — puras, testáveis, sem efeitos colaterais
# ---------------------------------------------------------------------------


def _check_safeguard_paths(changed_files: list[str], safeguard_paths: list[str]) -> bool:
    """Retorna True se qualquer arquivo alterado toca um path de salvaguarda.

    Matching por prefixo: permite tanto arquivos exatos quanto diretórios.
    Ex: '.github/' captura '.github/workflows/ci.yml'.
    """
    for f in changed_files:
        for prefix in safeguard_paths:
            if f == prefix or f.startswith(prefix):
                return True
    return False


def _combine_review_decision(verdict: str, risk: str, touches_safeguard: bool) -> str:
    """Combina veredito do revisor + risco + salvaguarda em decisão de merge.

    Retorna: 'auto_merge_candidate' | 'request_changes' | 'escalate'

    'auto_merge_candidate' ainda precisa passar pelo gate de CI (_should_auto_merge).

    Invariantes (inegociáveis):
      - touches_safeguard → 'escalate' independente do verdict (anti self-weakening).
      - risk == 'security' → 'escalate'.
      - verdict desconhecido → 'escalate' (fail-safe).
    """
    if touches_safeguard:
        return "escalate"
    if risk == "security":
        return "escalate"
    if verdict == "ESCALATE":
        return "escalate"
    if verdict == "APPROVE":
        return "auto_merge_candidate"
    if verdict == "REQUEST_CHANGES":
        return "request_changes"
    return "escalate"  # verdict desconhecido → fail-safe


# ---------------------------------------------------------------------------
# Helpers de revisão
# ---------------------------------------------------------------------------


def _log_review_result(result: dict[str, Any], pr_number: str, log: logging.Logger) -> None:
    """Loga veredito e findings do revisor em runs/."""
    log.info(
        "Revisor veredito PR #%s: %s | findings: %d | proposed_tests: %d",
        pr_number,
        result.get("verdict", "?"),
        len(result.get("findings", [])),
        len(result.get("proposed_tests", [])),
    )
    for finding in result.get("findings", []):
        log.info(
            "  [%s] %s: %s",
            finding.get("severity", "?").upper(),
            finding.get("invariant", "?"),
            finding.get("detail", ""),
        )


def _save_proposed_tests(pr_number: str, proposed_tests: list[str], log: logging.Logger) -> None:
    """Salva testes propostos pelo revisor — flywheel de eval (task-008 T3)."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"proposed-tests-{pr_number}.md"
    lines = [
        f"# Testes propostos pelo revisor adversarial\n\nPR: #{pr_number}\n\n"
    ]
    for t in proposed_tests:
        lines.append(f"- {t}\n")
    path.write_text("".join(lines), encoding="utf-8")
    log.info("Testes propostos salvos em %s", path)


def _run_driver_with_review_feedback(
    spec_path: Path,
    review_result: dict[str, Any],
    retry_n: int,
    log: logging.Logger,
) -> tuple[bool, str]:
    """Cria spec aumentada com feedback do revisor e roda o driver novamente.

    Escreve arquivo temporário <stem>-review-retry-<n>.md com findings + proposed_tests
    appended, chama _run_driver nele, limpa após.
    """
    original = spec_path.read_text(encoding="utf-8")
    findings_lines = "\n".join(
        f"- [{f.get('severity', '?').upper()}] {f.get('invariant', '?')}: {f.get('detail', '')}"
        for f in review_result.get("findings", [])
    )
    proposed_lines = "\n".join(f"- {t}" for t in review_result.get("proposed_tests", []))
    feedback_block = (
        f"\n\n---\n\n"
        f"# Feedback do Revisor Adversarial (retry {retry_n})\n\n"
        f"O revisor encontrou os seguintes problemas — corrija TODOS antes de finalizar:\n\n"
        f"## Findings\n\n{findings_lines or '(nenhum)'}\n\n"
        f"## Testes propostos (adicionar ao PR)\n\n{proposed_lines or '(nenhum)'}\n"
    )
    temp_path = spec_path.parent / f"{spec_path.stem}-review-retry-{retry_n}.md"
    temp_path.write_text(original + feedback_block, encoding="utf-8")
    log.info("Spec aumentada criada: %s", temp_path)
    try:
        return _run_driver(temp_path, log)
    finally:
        temp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Aguardar CI
# ---------------------------------------------------------------------------


def _wait_for_ci(pr_number: str, timeout_minutes: int, log: logging.Logger) -> bool:
    """Aguarda todos os checks do PR com gh pr checks --watch.

    Retorna True se todos os checks passaram; False em caso de falha ou timeout.
    """
    log.info("Aguardando CI para PR #%s (timeout: %d min)...", pr_number, timeout_minutes)
    try:
        result = subprocess.run(
            ["gh", "pr", "checks", pr_number, "--watch"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_minutes * 60,
        )
    except subprocess.TimeoutExpired:
        log.error("Timeout de %d min atingido aguardando CI do PR #%s.", timeout_minutes, pr_number)
        return False
    if result.returncode != 0:
        log.error(
            "CI falhou para PR #%s:\n%s",
            pr_number,
            (result.stdout + result.stderr)[-2000:],
        )
        return False
    log.info("CI verde para PR #%s.", pr_number)
    return True


# ---------------------------------------------------------------------------
# Merge + sync
# ---------------------------------------------------------------------------


def _merge_pr(pr_number: str, log: logging.Logger) -> bool:
    """Executa gh pr merge --merge. Nunca --admin, nunca force-merge."""
    result = subprocess.run(
        ["gh", "pr", "merge", pr_number, "--merge", "--delete-branch"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.error("gh pr merge falhou para PR #%s: %s", pr_number, result.stderr.strip())
        return False
    log.info("PR #%s mergeado com sucesso (merge commit).", pr_number)
    return True


def _sync_base(base_branch: str, log: logging.Logger) -> None:
    """git checkout <base> && git pull após merge bem-sucedido."""
    subprocess.run(["git", "checkout", base_branch], cwd=ROOT, capture_output=True, text=True)
    subprocess.run(["git", "pull"], cwd=ROOT, capture_output=True, text=True)
    log.info("Branch %s sincronizada após merge.", base_branch)


# ---------------------------------------------------------------------------
# Rodar o driver para uma spec
# ---------------------------------------------------------------------------


def _run_driver(spec_path: Path, log: logging.Logger) -> tuple[bool, str]:
    """Roda python driver.py <spec> e retorna (success, combined_output)."""
    driver_path = DRIVER_DIR / "driver.py"
    log.info("Rodando driver para: %s", spec_path)
    result = subprocess.run(
        [sys.executable, str(driver_path), str(spec_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    combined = result.stdout + result.stderr
    log.info("driver exit=%d", result.returncode)
    log.info("driver output:\n%s", combined[-3000:])
    return result.returncode == 0, combined


# ---------------------------------------------------------------------------
# Main queue loop
# ---------------------------------------------------------------------------


def run_queue(
    specs: list[Path],
    config: dict[str, Any],
    log: logging.Logger,
) -> int:
    """Processa specs em ordem. Retorna exit code."""
    base_branch = config.get("base_branch", "develop")
    ci_timeout = config.get("queue", {}).get("ci_timeout_minutes", 30)

    for i, spec_path in enumerate(specs, start=1):
        log.info("=== [%d/%d] Processando: %s ===", i, len(specs), spec_path)

        front = _load_front_matter(spec_path)
        risk = _parse_risk(front)
        log.info("Risk: %s", risk)

        if risk == "security":
            ok, output = _run_driver(spec_path, log)
            pr_number = _parse_pr_number(output)
            pr_ref = f"#{pr_number}" if pr_number else "(PR desconhecido)"
            if ok:
                log.warning(
                    "PR %s (security) aguardando revisão humana. "
                    "Lote PAUSADO — próximas tasks podem depender desta.",
                    pr_ref,
                )
            else:
                log.error("Driver falhou para spec security: %s", spec_path)
            return EXIT_PAUSED_SECURITY

        # risk == "low": roda driver → revisor adversarial → CI → decide merge
        ok, output = _run_driver(spec_path, log)
        if not ok:
            log.error("Driver falhou para spec: %s. Lote PAUSADO.", spec_path)
            return EXIT_DRIVER_FAILED

        pr_number = _parse_pr_number(output)
        if not pr_number:
            log.error(
                "Não foi possível extrair o número do PR do output do driver para: %s. "
                "[NEEDS CLARIFICATION] Verifique se o driver imprime a URL do PR de forma estável.",
                spec_path,
            )
            return EXIT_DRIVER_FAILED

        # --- Passo de revisão adversarial (task-008) ---
        reviewer_cfg = config.get("reviewer", {})
        safeguard_paths: list[str] = reviewer_cfg.get("safeguard_paths", [])
        reviewer_max_retries: int = reviewer_cfg.get("max_retries", 2)

        current_pr = pr_number
        review_result: dict[str, Any] = {}
        review_decision = "escalate"  # default pessimista; substituído abaixo

        for review_attempt in range(reviewer_max_retries + 1):
            changed_files = _get_pr_changed_files(current_pr)
            touches_safeguard = _check_safeguard_paths(changed_files, safeguard_paths)
            review_result = run_review(current_pr, spec_path, log, config)
            _log_review_result(review_result, current_pr, log)
            if review_result.get("proposed_tests"):
                _save_proposed_tests(current_pr, review_result["proposed_tests"], log)
            review_decision = _combine_review_decision(
                review_result["verdict"], risk, touches_safeguard
            )
            if review_decision != "request_changes":
                break
            if review_attempt >= reviewer_max_retries:
                log.error(
                    "REQUEST_CHANGES persistiu após %d revisões. ESCALANDO.", reviewer_max_retries
                )
                review_decision = "escalate"
                break
            log.warning(
                "REQUEST_CHANGES: re-rodando implementador (revisão %d/%d).",
                review_attempt + 1, reviewer_max_retries,
            )
            ok, output = _run_driver_with_review_feedback(
                spec_path, review_result, review_attempt + 1, log
            )
            if not ok:
                log.error("Driver falhou no re-run pós-review. Lote PAUSADO.")
                return EXIT_DRIVER_FAILED
            new_pr = _parse_pr_number(output)
            if not new_pr:
                log.error("Não foi possível extrair PR do re-run pós-review.")
                return EXIT_DRIVER_FAILED
            current_pr = new_pr

        if review_decision == "escalate":
            log.error(
                "Revisor ESCALOU PR #%s. Lote PAUSADO. PR aberto para revisão humana.",
                current_pr,
            )
            return EXIT_REVIEWER_ESCALATED
        # --- Fim do passo de revisão ---

        checks_passed = _wait_for_ci(current_pr, ci_timeout, log)

        if not _should_auto_merge(risk, checks_passed, base_branch):
            if not checks_passed:
                log.error(
                    "CI falhou para PR #%s (risk=low). Lote PAUSADO. PR aberto para revisão humana.",
                    current_pr,
                )
                return EXIT_CI_FAILED
            log.error(
                "Recusa de auto-merge: base_branch='%s' != 'develop'. PR #%s aberto para revisão.",
                base_branch,
                current_pr,
            )
            return EXIT_CI_FAILED

        if not _merge_pr(current_pr, log):
            return EXIT_DRIVER_FAILED

        _sync_base(base_branch, log)
        log.info("Task %s concluída e mergeada.", spec_path.name)

    log.info("=== Queue completa: %d task(s) processada(s). ===", len(specs))
    return EXIT_OK


# ---------------------------------------------------------------------------
# Carregamento de queue.txt
# ---------------------------------------------------------------------------


def _load_queue_from_file(queue_file: Path) -> list[Path]:
    lines = queue_file.read_text(encoding="utf-8").splitlines()
    return [
        Path(line.strip())
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Queue runner L2 — executa specs em ordem com auto-merge gateado por risk + CI."
    )
    parser.add_argument(
        "specs",
        nargs="*",
        type=Path,
        help="Specs a processar (em ordem). Se omitido, lê de --queue-file.",
    )
    parser.add_argument(
        "--queue-file",
        type=Path,
        default=DRIVER_DIR / "queue.txt",
        help="Arquivo com lista de specs (um caminho por linha). Padrão: queue.txt",
    )
    args = parser.parse_args()

    log, log_path = _setup_logging("queue")
    log.info("=== queue_runner L2 ===")
    log.info("Log: %s", log_path)

    specs: list[Path] = list(args.specs)
    if not specs:
        if args.queue_file.exists():
            specs = _load_queue_from_file(args.queue_file)
            log.info("Specs carregadas de %s: %d", args.queue_file, len(specs))
        else:
            log.error("Nenhuma spec fornecida e %s não existe.", args.queue_file)
            return EXIT_NO_QUEUE

    if not specs:
        log.warning("Queue vazia — nada a fazer.")
        return EXIT_OK

    config = _load_config()
    return run_queue(specs, config, log)


if __name__ == "__main__":
    sys.exit(main())
