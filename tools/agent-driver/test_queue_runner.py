"""Testes do queue_runner — sem subprocess real, sem gh, sem driver (tudo mockado).

Invariantes verificadas:
  - _parse_risk: com e sem campo risk; fail-safe = security [crítico]
  - _should_auto_merge: low + success + develop → True; demais → False
  - NUNCA decide mergear se base != develop
  - _parse_pr_number: extrai corretamente de URL do gh
"""

import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import queue_runner  # noqa: E402


# ---------------------------------------------------------------------------
# _parse_risk
# ---------------------------------------------------------------------------


def test_parse_risk_explicit_low():
    assert queue_runner._parse_risk({"risk": "low"}) == "low"


def test_parse_risk_explicit_security():
    assert queue_runner._parse_risk({"risk": "security"}) == "security"


def test_parse_risk_missing_defaults_to_security():
    """Spec SEM campo risk → security (fail-safe crítico)."""
    assert queue_runner._parse_risk({}) == "security"


def test_parse_risk_unknown_value_defaults_to_security():
    """Valor desconhecido (ex: 'medium') → security (fail-safe)."""
    assert queue_runner._parse_risk({"risk": "medium"}) == "security"


def test_parse_risk_none_value_defaults_to_security():
    """Valor None → security."""
    assert queue_runner._parse_risk({"risk": None}) == "security"


def test_parse_risk_empty_dict():
    assert queue_runner._parse_risk({}) == "security"


# ---------------------------------------------------------------------------
# _should_auto_merge — função pura, sem efeitos colaterais
# ---------------------------------------------------------------------------


def test_auto_merge_low_success_develop():
    """Única combinação que deve retornar True."""
    assert queue_runner._should_auto_merge("low", True, "develop") is True


def test_auto_merge_low_failure_develop():
    """CI falhou → não mergeia, para o lote."""
    assert queue_runner._should_auto_merge("low", False, "develop") is False


def test_auto_merge_security_success_develop():
    """security NUNCA auto-mergeia, mesmo com CI verde."""
    assert queue_runner._should_auto_merge("security", True, "develop") is False


def test_auto_merge_security_failure_develop():
    assert queue_runner._should_auto_merge("security", False, "develop") is False


def test_auto_merge_low_success_main():
    """NUNCA auto-mergeia em main."""
    assert queue_runner._should_auto_merge("low", True, "main") is False


def test_auto_merge_low_success_staging():
    """NUNCA auto-mergeia em staging."""
    assert queue_runner._should_auto_merge("low", True, "staging") is False


def test_auto_merge_low_success_other_branch():
    """Qualquer branch != 'develop' → False."""
    assert queue_runner._should_auto_merge("low", True, "feature/xyz") is False


def test_auto_merge_low_success_empty_base():
    assert queue_runner._should_auto_merge("low", True, "") is False


# ---------------------------------------------------------------------------
# _parse_pr_number
# ---------------------------------------------------------------------------


def test_parse_pr_number_from_log_line():
    output = "2026-06-03 [INFO] gh pr create stdout: https://github.com/org/repo/pull/42"
    assert queue_runner._parse_pr_number(output) == "42"


def test_parse_pr_number_direct_url():
    output = "https://github.com/logikos/recognition/pull/123\n"
    assert queue_runner._parse_pr_number(output) == "123"


def test_parse_pr_number_not_found():
    assert queue_runner._parse_pr_number("nenhuma url aqui") is None


def test_parse_pr_number_multiline():
    output = "... building ...\nPR criado: https://github.com/x/y/pull/99\nDone."
    assert queue_runner._parse_pr_number(output) == "99"


def test_parse_pr_number_large_number():
    output = "https://github.com/a/b/pull/1042"
    assert queue_runner._parse_pr_number(output) == "1042"


# ---------------------------------------------------------------------------
# Invariante: _should_auto_merge nunca retorna True para base != develop
# ---------------------------------------------------------------------------


def test_never_auto_merge_non_develop_bases():
    """Propriedade: para qualquer base != 'develop', never True."""
    non_develop_bases = ["main", "staging", "master", "release", "feature/x", "", "DEVELOP"]
    for base in non_develop_bases:
        assert queue_runner._should_auto_merge("low", True, base) is False, (
            f"_should_auto_merge deveria ser False para base='{base}'"
        )


# ---------------------------------------------------------------------------
# Regressão: safeguard_paths do config REAL cobre os paths esperados
# Carrega o config.yaml de verdade — divergência futura quebra este teste.
# ---------------------------------------------------------------------------

def _load_real_safeguard_paths() -> list[str]:
    import yaml
    cfg_path = HERE / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    paths = cfg.get("reviewer", {}).get("safeguard_paths", [])
    # yaml pode carregar comentários inline como parte do valor; strip após '#'
    return [p.split("#")[0].strip() for p in paths]


def test_safeguard_invariant_suite_protected():
    """test_edge_invariants.py deve escalar (suíte de invariantes está em tests/security/)."""
    paths = _load_real_safeguard_paths()
    assert queue_runner._check_safeguard_paths(
        ["services/api/tests/security/test_edge_invariants.py"], paths
    ) is True


def test_safeguard_helpers_tenant_protected():
    """_helpers_tenant.py deve escalar."""
    paths = _load_real_safeguard_paths()
    assert queue_runner._check_safeguard_paths(
        ["services/api/tests/security/_helpers_tenant.py"], paths
    ) is True


def test_safeguard_config_yaml_protected():
    """O próprio config.yaml do driver deve escalar."""
    paths = _load_real_safeguard_paths()
    assert queue_runner._check_safeguard_paths(
        ["tools/agent-driver/config.yaml"], paths
    ) is True


def test_safeguard_reviewer_protected():
    """reviewer.py deve escalar."""
    paths = _load_real_safeguard_paths()
    assert queue_runner._check_safeguard_paths(
        ["tools/agent-driver/reviewer.py"], paths
    ) is True


def test_safeguard_migration_protected():
    """Migrations devem escalar."""
    paths = _load_real_safeguard_paths()
    assert queue_runner._check_safeguard_paths(
        ["infra/migrations/050_edge_sites.sql"], paths
    ) is True


def test_safeguard_feature_route_not_protected():
    """Arquivo de feature comum NÃO deve escalar."""
    paths = _load_real_safeguard_paths()
    assert queue_runner._check_safeguard_paths(
        ["services/api/app/api/v1/edge/routes.py"], paths
    ) is False


# ---------------------------------------------------------------------------
# _build_review_feedback_str — nova função pura (sem arquivo)
# ---------------------------------------------------------------------------


def test_build_review_feedback_str_contains_findings_and_tests():
    """Feedback string deve incluir findings e proposed_tests."""
    review_result = {
        "findings": [
            {"severity": "high", "invariant": "C-01", "detail": "missing tenant_id filter"}
        ],
        "proposed_tests": ["test_cross_tenant_isolation"],
    }
    feedback = queue_runner._build_review_feedback_str(review_result, retry_n=1)
    assert "missing tenant_id filter" in feedback
    assert "test_cross_tenant_isolation" in feedback
    assert "REQUEST_CHANGES" in feedback


def test_build_review_feedback_str_includes_retry_number():
    """Número do retry deve constar no feedback string."""
    feedback = queue_runner._build_review_feedback_str(
        {"findings": [], "proposed_tests": []}, retry_n=3
    )
    assert "3" in feedback


def test_build_review_feedback_str_empty_review():
    """Feedback sem findings/proposed_tests deve conter placeholders, não travar."""
    feedback = queue_runner._build_review_feedback_str(
        {"findings": [], "proposed_tests": []}, retry_n=1
    )
    assert "nenhum" in feedback
    assert isinstance(feedback, str)
    assert len(feedback) > 0


def test_build_review_feedback_str_no_file_side_effects(monkeypatch):
    """_build_review_feedback_str é pura — não escreve nenhum arquivo."""
    written: list[str] = []
    orig_write = Path.write_text

    def spy_write(self, content, *args, **kwargs):  # type: ignore[override]
        written.append(str(self))
        return orig_write(self, content, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", spy_write)
    queue_runner._build_review_feedback_str(
        {"findings": [{"severity": "low", "invariant": "C-01", "detail": "x"}], "proposed_tests": []},
        retry_n=1,
    )
    assert len(written) == 0, f"_build_review_feedback_str escreveu arquivo(s): {written}"


# ---------------------------------------------------------------------------
# _run_driver_with_review_feedback foi removida (escrevia arquivo temp)
# ---------------------------------------------------------------------------


def test_file_writing_retry_function_removed():
    """_run_driver_with_review_feedback (escrevia arquivo temp) deve ter sido removida."""
    assert not hasattr(queue_runner, "_run_driver_with_review_feedback"), (
        "_run_driver_with_review_feedback ainda existe — removê-la é parte central do fix"
    )


# ---------------------------------------------------------------------------
# Retry in-memory: após max_retries REQUEST_CHANGES → escalate (sem loop infinito)
# ---------------------------------------------------------------------------


def test_max_retries_request_changes_escalates(tmp_path, monkeypatch):
    """Após max_retries de REQUEST_CHANGES consecutivos, run_queue retorna ESCALATE."""
    spec = tmp_path / "task-test.md"
    spec.write_text("---\nrisk: low\n---\n# Test task\n\nDo something.\n")

    config = {
        "base_branch": "develop",
        "model": "claude-test",
        "allowed_tools": [],
        "reviewer": {
            "max_retries": 1,
            "safeguard_paths": [],
            "model": "claude-test",
            "allowed_tools": [],
        },
        "queue": {"ci_timeout_minutes": 1},
        "checks": {"default": ["true"]},
    }
    log = logging.getLogger("test_escalate")

    monkeypatch.setattr(queue_runner, "_run_driver",
                        lambda *a, **k: (True, "https://github.com/x/y/pull/1"))
    monkeypatch.setattr(queue_runner, "_get_pr_changed_files", lambda *a, **k: [])
    monkeypatch.setattr(queue_runner, "run_review", lambda *a, **k: {
        "verdict": "REQUEST_CHANGES",
        "findings": [{"severity": "low", "invariant": "test", "detail": "test detail"}],
        "proposed_tests": [],
    })
    monkeypatch.setattr(queue_runner, "_save_proposed_tests", lambda *a, **k: None)
    monkeypatch.setattr(queue_runner, "run_implementer_retry", lambda *a, **k: (True, ""))
    monkeypatch.setattr(queue_runner, "commit_retry_on_branch", lambda *a, **k: True)
    monkeypatch.setattr(queue_runner, "_load_spec_full", lambda p: ({}, "body"))

    exit_code = queue_runner.run_queue([spec], config, log)
    assert exit_code == queue_runner.EXIT_REVIEWER_ESCALATED


def test_retry_does_not_extract_new_pr_number():
    """No retry in-memory, current_pr não muda — _parse_pr_number não é chamado após retry.

    Verifica via inspeção de source: a extração de 'new_pr' foi removida do loop de retry.
    """
    import inspect
    source = inspect.getsource(queue_runner.run_queue)
    assert "new_pr = _parse_pr_number" not in source, (
        "new_pr = _parse_pr_number encontrado no loop — no retry in-memory, o PR não muda"
    )
