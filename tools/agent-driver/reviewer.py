"""Revisor adversarial — READ-ONLY gate de merge.

Analisa o diff de um PR em busca de falhas nos invariantes, constitution e threat-model.
Emite veredito estruturado JSON. NUNCA edita código, NUNCA mergeia.

Separação de funções (inegociável):
  - Modelo diferente do implementador (Opus vs Sonnet).
  - allowedTools somente leitura: Read, Glob, Grep, Bash(git diff:*), Bash(git log:*).
  - Saída JSON estruturada com fail-safe ESCALATE em parse inválido.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

DRIVER_DIR = Path(__file__).resolve().parent
ROOT = DRIVER_DIR.parent.parent
CONFIG_PATH = DRIVER_DIR / "config.yaml"
CONSTITUTION_PATH = ROOT / "constitution.md"

_THREAT_CHECKLIST = """\
## Checklist de Ameaças (verificar CADA item independentemente da spec)

1. **Multi-tenant**: tenant_id extraído do servidor (JWT/banco), NUNCA do body/claims do cliente?
   - Toda query filtra por tenant_id?
   - Sem vazamento cross-tenant?

2. **Auth**: Toda rota protegida verifica assinatura do token de verdade?
   - Sem bypass por header customizado ou parâmetro de query?
   - Token expirado é rejeitado?

3. **Token one-time** (se aplicável): operação atômica? Dupla submissão impossível?

4. **Segredos**: guardados como hash (bcrypt/argon2)? Nunca em plaintext?
   - Sem print() com dados sensíveis? Sem log de passwords/tokens?

5. **SQL**: parametrizado? Zero f-string de input do usuário?

6. **Testes cross-tenant**: prova que usuário A não vê dados de usuário B?

7. **Teste de auth ausente**: rejeita token ausente/inválido/expirado?

8. **Migrations**: forward-only? Idempotentes? Toda tabela nova tem tenant_id?

9. **CORS**: origins explícitos? Nunca bare CORS(app)?

10. **Segredos em código**: sem API keys/passwords/tokens hardcoded?
"""

_REVIEWER_INSTRUCTIONS = """\
Você é um revisor adversarial de segurança e qualidade.
Sua missão é FALSIFICAR invariantes — encontrar buracos que o implementador não viu.
NÃO confie que a spec está correta. Verifique o threat-model independentemente.
NÃO edite código. NÃO execute comandos destrutivos. APENAS leia e analise.

Responda EXCLUSIVAMENTE com JSON válido, sem markdown adicional, sem texto fora do JSON:
{
  "verdict": "APPROVE|REQUEST_CHANGES|ESCALATE",
  "findings": [
    {"invariant": "nome", "severity": "critical|high|medium|low", "detail": "detalhe específico"}
  ],
  "proposed_tests": ["descrição do teste ausente"]
}

Critérios de veredito:
- APPROVE: sem findings críticos/altos, threat-model ok, testes adequados.
- REQUEST_CHANGES: findings que o implementador pode corrigir.
- ESCALATE: falha crítica de segurança, vazamento cross-tenant, auth bypassável, ou qualquer dúvida séria.
"""


def _load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_pr_diff(pr_number: str) -> str:
    """Obtém o diff completo do PR via gh."""
    try:
        result = subprocess.run(
            ["gh", "pr", "diff", pr_number],
            capture_output=True, text=True, cwd=ROOT, timeout=60,
        )
        if result.returncode == 0:
            diff = result.stdout
            truncated = diff[:12000]
            return truncated + ("... (truncado)" if len(diff) > 12000 else "")
        return f"(falha ao obter diff: {result.stderr.strip()[:500]})"
    except subprocess.TimeoutExpired:
        return "(timeout ao obter diff do PR)"
    except Exception as exc:  # noqa: BLE001
        return f"(erro: {exc})"


def _get_pr_changed_files(pr_number: str) -> list[str]:
    """Lista os arquivos alterados no PR (para checagem de safeguard paths)."""
    try:
        result = subprocess.run(
            ["gh", "pr", "diff", pr_number, "--name-only"],
            capture_output=True, text=True, cwd=ROOT, timeout=60,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        return []
    except Exception:  # noqa: BLE001
        return []


def _build_review_prompt(pr_number: str, spec_text: str, diff: str) -> str:
    constitution = (
        CONSTITUTION_PATH.read_text(encoding="utf-8")
        if CONSTITUTION_PATH.exists()
        else "(constitution.md ausente)"
    )
    return (
        f"{_REVIEWER_INSTRUCTIONS}\n\n"
        f"# Revisão adversarial — PR #{pr_number}\n\n"
        f"## Constitution (invariantes inegociáveis)\n\n{constitution}\n\n"
        f"## Spec da tarefa\n\n{spec_text}\n\n"
        f"## Diff do PR\n\n```diff\n{diff}\n```\n\n"
        f"{_THREAT_CHECKLIST}\n\n"
        "Analise o diff. Tente FALSIFICAR cada invariante. "
        "Emita EXCLUSIVAMENTE o JSON de veredito, sem texto adicional."
    )


def _escalate_result(detail: str = "Revisor não retornou JSON válido — fail-safe ESCALATE.") -> dict[str, Any]:
    return {
        "verdict": "ESCALATE",
        "findings": [{"invariant": "parse-error", "severity": "critical", "detail": detail}],
        "proposed_tests": [],
    }


def _parse_review_output(raw: str, log: logging.Logger) -> dict[str, Any]:
    """Parse robusto do output do revisor. Qualquer falha → ESCALATE (fail-safe)."""
    text: str = raw.strip()

    # claude --output-format json wraps output in {"result": "..."}
    try:
        envelope = json.loads(text)
        if isinstance(envelope, dict) and "result" in envelope:
            inner = envelope["result"]
            # result may itself be a dict (already parsed) or a string
            if isinstance(inner, dict):
                data = inner
                return _validate_review_data(data, log)
            elif isinstance(inner, str):
                text = inner.strip()
    except (json.JSONDecodeError, TypeError):
        pass

    # Try direct parse of text
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # Try to extract JSON block from text
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            log.error("Revisor: nenhum JSON encontrado no output. ESCALATE fail-safe.")
            return _escalate_result()
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            log.error("Revisor: JSON extraído inválido. ESCALATE fail-safe.")
            return _escalate_result()

    return _validate_review_data(data, log)


def _validate_review_data(data: Any, log: logging.Logger) -> dict[str, Any]:
    if not isinstance(data, dict):
        log.error("Revisor: output não é dict. ESCALATE fail-safe.")
        return _escalate_result()

    verdict = data.get("verdict")
    if verdict not in ("APPROVE", "REQUEST_CHANGES", "ESCALATE"):
        log.error("Revisor: verdict inválido '%s'. ESCALATE fail-safe.", verdict)
        return _escalate_result(f"verdict inválido: {verdict!r}")

    return {
        "verdict": verdict,
        "findings": data.get("findings", []),
        "proposed_tests": data.get("proposed_tests", []),
    }


def run_review(
    pr_number: str,
    spec_path: Path,
    log: logging.Logger,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Chama o Claude Opus para revisar o PR. Retorna resultado parseado.

    Em qualquer falha de chamada ou parse → ESCALATE (fail-safe).
    O revisor é READ-ONLY: allowedTools não inclui Edit/Write/merge.
    """
    if config is None:
        config = _load_config()

    reviewer_cfg = config.get("reviewer", {})
    reviewer_model = reviewer_cfg.get("model", "claude-opus-4-6")
    allowed_tools: list[str] = reviewer_cfg.get("allowed_tools", [
        "Read", "Glob", "Grep", "Bash(git diff:*)", "Bash(git log:*)",
    ])

    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.exists() else "(spec ausente)"
    diff = _get_pr_diff(pr_number)
    prompt = _build_review_prompt(pr_number, spec_text, diff)

    cmd = [
        "claude",
        "-p", prompt,
        "--model", reviewer_model,
        "--output-format", "json",
        "--permission-mode", "acceptEdits",
        "--allowedTools", ",".join(allowed_tools),
    ]

    log.info("Revisor: chamando %s para PR #%s", reviewer_model, pr_number)
    try:
        result = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        log.error("Revisor: timeout. ESCALATE fail-safe.")
        return _escalate_result("Timeout ao chamar revisor.")
    except Exception as exc:  # noqa: BLE001
        log.error("Revisor: erro ao chamar claude: %s. ESCALATE fail-safe.", exc)
        return _escalate_result(f"Erro ao chamar revisor: {exc}")

    log.info("Revisor exit=%d", result.returncode)
    if result.returncode != 0:
        log.warning("Revisor saiu com código não-zero. Tentando parse mesmo assim.")

    return _parse_review_output(result.stdout, log)
