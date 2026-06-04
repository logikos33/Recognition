"""Testes do revisor adversarial (task-008) — sem subprocess real, sem gh, sem claude.

Invariantes verificadas (eval da spec):
  - decisão: APPROVE+low+CI verde → merge; REQUEST_CHANGES → loop; ESCALATE → pausa.
  - forçar ESCALATE quando diff toca constitution.md / invariant suite / reviewer /
    driver / migrations / .github — MESMO com verdict=APPROVE. [anti self-weakening]
  - forçar ESCALATE quando risk=security (mesmo APPROVE).
  - JSON inválido do revisor → ESCALATE (fail-safe).
  - reviewer é read-only: allowedTools não contém Edit/Write/merge.
"""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import queue_runner  # noqa: E402
import reviewer  # noqa: E402

_LOG = logging.getLogger("test_reviewer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_log() -> logging.Logger:
    log = logging.getLogger(f"test.{id(object())}")
    log.addHandler(logging.NullHandler())
    return log


# ---------------------------------------------------------------------------
# _parse_review_output — fail-safe ESCALATE em qualquer parse inválido
# ---------------------------------------------------------------------------


def test_parse_valid_approve():
    raw = json.dumps({"verdict": "APPROVE", "findings": [], "proposed_tests": []})
    result = reviewer._parse_review_output(raw, _make_log())
    assert result["verdict"] == "APPROVE"
    assert result["findings"] == []


def test_parse_valid_request_changes():
    data = {
        "verdict": "REQUEST_CHANGES",
        "findings": [{"invariant": "multi-tenant", "severity": "high", "detail": "missing filter"}],
        "proposed_tests": ["test cross-tenant isolation"],
    }
    result = reviewer._parse_review_output(json.dumps(data), _make_log())
    assert result["verdict"] == "REQUEST_CHANGES"
    assert len(result["findings"]) == 1
    assert result["proposed_tests"] == ["test cross-tenant isolation"]


def test_parse_valid_escalate():
    raw = json.dumps({"verdict": "ESCALATE", "findings": [], "proposed_tests": []})
    result = reviewer._parse_review_output(raw, _make_log())
    assert result["verdict"] == "ESCALATE"


def test_parse_invalid_json_returns_escalate():
    """JSON inválido → ESCALATE (fail-safe crítico)."""
    result = reviewer._parse_review_output("not json at all", _make_log())
    assert result["verdict"] == "ESCALATE"
    assert result["findings"][0]["invariant"] == "parse-error"


def test_parse_empty_string_returns_escalate():
    result = reviewer._parse_review_output("", _make_log())
    assert result["verdict"] == "ESCALATE"


def test_parse_unknown_verdict_returns_escalate():
    """Verdict desconhecido → ESCALATE (fail-safe)."""
    raw = json.dumps({"verdict": "MAYBE", "findings": [], "proposed_tests": []})
    result = reviewer._parse_review_output(raw, _make_log())
    assert result["verdict"] == "ESCALATE"


def test_parse_missing_verdict_returns_escalate():
    raw = json.dumps({"findings": [], "proposed_tests": []})
    result = reviewer._parse_review_output(raw, _make_log())
    assert result["verdict"] == "ESCALATE"


def test_parse_claude_envelope_format():
    """claude --output-format json envolve resultado em {result: ...}."""
    inner = json.dumps({"verdict": "APPROVE", "findings": [], "proposed_tests": []})
    envelope = json.dumps({"result": inner, "session_id": "abc"})
    result = reviewer._parse_review_output(envelope, _make_log())
    assert result["verdict"] == "APPROVE"


def test_parse_json_embedded_in_text():
    """JSON embedded em texto com markdown → extraído corretamente."""
    raw = 'Análise completa:\n```\n{"verdict": "REQUEST_CHANGES", "findings": [], "proposed_tests": []}\n```'
    result = reviewer._parse_review_output(raw, _make_log())
    assert result["verdict"] == "REQUEST_CHANGES"


# ---------------------------------------------------------------------------
# _check_safeguard_paths — anti self-weakening
# ---------------------------------------------------------------------------


def test_safeguard_constitution_exact():
    """constitution.md é safeguard path."""
    assert queue_runner._check_safeguard_paths(
        ["constitution.md"], ["constitution.md"]
    ) is True


def test_safeguard_github_workflow():
    """.github/ captura qualquer arquivo dentro de .github/."""
    assert queue_runner._check_safeguard_paths(
        [".github/workflows/ci.yml"], [".github/"]
    ) is True


def test_safeguard_reviewer_self():
    """Toque no próprio reviewer.py → safeguard."""
    assert queue_runner._check_safeguard_paths(
        ["tools/agent-driver/reviewer.py"],
        ["tools/agent-driver/reviewer.py"],
    ) is True


def test_safeguard_driver():
    assert queue_runner._check_safeguard_paths(
        ["tools/agent-driver/driver.py"],
        ["tools/agent-driver/driver.py"],
    ) is True


def test_safeguard_queue_runner_self():
    assert queue_runner._check_safeguard_paths(
        ["tools/agent-driver/queue_runner.py"],
        ["tools/agent-driver/queue_runner.py"],
    ) is True


def test_safeguard_migrations():
    assert queue_runner._check_safeguard_paths(
        ["infra/migrations/042_foo.sql"], ["infra/migrations/"]
    ) is True


def test_safeguard_invariant_suite():
    assert queue_runner._check_safeguard_paths(
        ["services/api/tests/edge/test_edge_invariants.py"],
        ["services/api/tests/edge/"],
    ) is True


def test_safeguard_clean_file():
    """Arquivo não-safeguard não dispara escalate."""
    assert queue_runner._check_safeguard_paths(
        ["frontend/src/App.tsx"],
        ["constitution.md", ".github/", "infra/migrations/"],
    ) is False


def test_safeguard_empty_changed_files():
    assert queue_runner._check_safeguard_paths([], ["constitution.md"]) is False


def test_safeguard_empty_paths_list():
    assert queue_runner._check_safeguard_paths(["constitution.md"], []) is False


# ---------------------------------------------------------------------------
# _combine_review_decision — tabela de decisão completa
# ---------------------------------------------------------------------------


def test_decision_approve_low_no_safeguard():
    """APPROVE + low + sem safeguard → auto_merge_candidate."""
    assert queue_runner._combine_review_decision("APPROVE", "low", False) == "auto_merge_candidate"


def test_decision_request_changes_low():
    """REQUEST_CHANGES → request_changes (loop de feedback)."""
    assert queue_runner._combine_review_decision("REQUEST_CHANGES", "low", False) == "request_changes"


def test_decision_escalate_verdict():
    """ESCALATE do revisor → escalate."""
    assert queue_runner._combine_review_decision("ESCALATE", "low", False) == "escalate"


def test_decision_safeguard_overrides_approve():
    """Safeguard path tocado → escalate MESMO com APPROVE (anti self-weakening)."""
    assert queue_runner._combine_review_decision("APPROVE", "low", True) == "escalate"


def test_decision_safeguard_overrides_request_changes():
    assert queue_runner._combine_review_decision("REQUEST_CHANGES", "low", True) == "escalate"


def test_decision_risk_security_overrides_approve():
    """risk=security → escalate MESMO com APPROVE."""
    assert queue_runner._combine_review_decision("APPROVE", "security", False) == "escalate"


def test_decision_risk_security_overrides_request_changes():
    assert queue_runner._combine_review_decision("REQUEST_CHANGES", "security", False) == "escalate"


def test_decision_unknown_verdict_escalates():
    """Verdict desconhecido → escalate (fail-safe)."""
    assert queue_runner._combine_review_decision("UNKNOWN", "low", False) == "escalate"


# ---------------------------------------------------------------------------
# Combinação com _should_auto_merge: APPROVE+low+CI verde+develop → merge
# ---------------------------------------------------------------------------


def test_full_pipeline_approve_low_ci_green():
    """APPROVE+low+CI verde+develop: review OK + merge OK."""
    decision = queue_runner._combine_review_decision("APPROVE", "low", False)
    assert decision == "auto_merge_candidate"
    # Gate final de CI e base
    assert queue_runner._should_auto_merge("low", True, "develop") is True


def test_full_pipeline_approve_low_ci_failed():
    """APPROVE do revisor mas CI falhou → NÃO mergeia."""
    decision = queue_runner._combine_review_decision("APPROVE", "low", False)
    assert decision == "auto_merge_candidate"
    assert queue_runner._should_auto_merge("low", False, "develop") is False


def test_full_pipeline_escalate_never_merges():
    """ESCALATE → escalate; _should_auto_merge não é chamado."""
    decision = queue_runner._combine_review_decision("ESCALATE", "low", False)
    assert decision == "escalate"
    assert decision != "auto_merge_candidate"


# ---------------------------------------------------------------------------
# Reviewer allowedTools são READ-ONLY (sem Edit/Write/merge)
# ---------------------------------------------------------------------------


def test_reviewer_allowed_tools_read_only():
    """Os allowedTools do revisor NÃO devem conter ferramentas de escrita ou merge."""
    config = queue_runner._load_config()
    allowed: list[str] = config.get("reviewer", {}).get("allowed_tools", [])
    assert allowed, "reviewer.allowed_tools deve estar configurado no config.yaml"
    forbidden_exact = {"Edit", "Write", "NotebookEdit"}
    for tool in allowed:
        assert tool not in forbidden_exact, f"Ferramenta de escrita proibida: {tool!r}"
        assert "merge" not in tool.lower(), f"'merge' proibido em tool: {tool!r}"
        assert "push" not in tool.lower(), f"'push' proibido em tool: {tool!r}"
        assert "commit" not in tool.lower(), f"'commit' proibido em tool: {tool!r}"


# ---------------------------------------------------------------------------
# Integração: run_queue com reviewer mockado
# ---------------------------------------------------------------------------


def _make_config(reviewer_max_retries: int = 1) -> dict:
    return {
        "base_branch": "develop",
        "max_retries": 3,
        "queue": {"ci_timeout_minutes": 1},
        "reviewer": {
            "safeguard_paths": ["constitution.md", ".github/"],
            "max_retries": reviewer_max_retries,
            "model": "claude-opus-4-6",
            "allowed_tools": ["Read", "Grep"],
        },
    }


def _make_spec(tmp_path: Path, risk: str = "low") -> Path:
    spec = tmp_path / "task-test.md"
    spec.write_text(f"---\nrisk: {risk}\n---\n# Test\n", encoding="utf-8")
    return spec


def test_run_queue_approve_auto_merges(tmp_path: Path):
    """APPROVE + CI verde + develop → merge automático."""
    spec = _make_spec(tmp_path)
    log = _make_log()

    with (
        patch.object(queue_runner, "_run_driver", return_value=(True, "https://github.com/x/y/pull/42")),
        patch.object(queue_runner, "run_review", return_value={"verdict": "APPROVE", "findings": [], "proposed_tests": []}),
        patch.object(queue_runner, "_get_pr_changed_files", return_value=[]),
        patch.object(queue_runner, "_wait_for_ci", return_value=True),
        patch.object(queue_runner, "_merge_pr", return_value=True),
        patch.object(queue_runner, "_sync_base"),
    ):
        result = queue_runner.run_queue([spec], _make_config(), log)

    assert result == queue_runner.EXIT_OK


def test_run_queue_escalate_stops(tmp_path: Path):
    """ESCALATE do revisor → EXIT_REVIEWER_ESCALATED, não mergeia."""
    spec = _make_spec(tmp_path)
    log = _make_log()
    merge_mock = MagicMock()

    with (
        patch.object(queue_runner, "_run_driver", return_value=(True, "https://github.com/x/y/pull/10")),
        patch.object(queue_runner, "run_review", return_value={"verdict": "ESCALATE", "findings": [], "proposed_tests": []}),
        patch.object(queue_runner, "_get_pr_changed_files", return_value=[]),
        patch.object(queue_runner, "_wait_for_ci", return_value=True),
        patch.object(queue_runner, "_merge_pr", merge_mock),
        patch.object(queue_runner, "_sync_base"),
    ):
        result = queue_runner.run_queue([spec], _make_config(), log)

    assert result == queue_runner.EXIT_REVIEWER_ESCALATED
    merge_mock.assert_not_called()


def test_run_queue_safeguard_path_forces_escalate(tmp_path: Path):
    """Diff toca constitution.md → ESCALATE mesmo com APPROVE."""
    spec = _make_spec(tmp_path)
    log = _make_log()
    merge_mock = MagicMock()

    with (
        patch.object(queue_runner, "_run_driver", return_value=(True, "https://github.com/x/y/pull/11")),
        patch.object(queue_runner, "run_review", return_value={"verdict": "APPROVE", "findings": [], "proposed_tests": []}),
        patch.object(queue_runner, "_get_pr_changed_files", return_value=["constitution.md"]),
        patch.object(queue_runner, "_wait_for_ci", return_value=True),
        patch.object(queue_runner, "_merge_pr", merge_mock),
        patch.object(queue_runner, "_sync_base"),
    ):
        result = queue_runner.run_queue([spec], _make_config(), log)

    assert result == queue_runner.EXIT_REVIEWER_ESCALATED
    merge_mock.assert_not_called()


def test_run_queue_request_changes_retries_then_approves(tmp_path: Path):
    """REQUEST_CHANGES → re-roda implementador → APPROVE → merge."""
    spec = _make_spec(tmp_path)
    log = _make_log()

    review_calls = []

    def mock_review(pr, spec_path, lg, cfg):
        review_calls.append(pr)
        if len(review_calls) == 1:
            return {"verdict": "REQUEST_CHANGES", "findings": [{"invariant": "auth", "severity": "medium", "detail": "missing test"}], "proposed_tests": ["add auth test"]}
        return {"verdict": "APPROVE", "findings": [], "proposed_tests": []}

    driver_calls = []

    def mock_driver(sp, lg):
        driver_calls.append(str(sp))
        pr_num = 42 + len(driver_calls)
        return True, f"https://github.com/x/y/pull/{pr_num}"

    with (
        patch.object(queue_runner, "_run_driver", mock_driver),
        patch.object(queue_runner, "run_review", mock_review),
        patch.object(queue_runner, "_get_pr_changed_files", return_value=[]),
        patch.object(queue_runner, "_wait_for_ci", return_value=True),
        patch.object(queue_runner, "_merge_pr", return_value=True),
        patch.object(queue_runner, "_sync_base"),
        patch.object(queue_runner, "_save_proposed_tests"),
    ):
        result = queue_runner.run_queue([spec], _make_config(reviewer_max_retries=1), log)

    assert result == queue_runner.EXIT_OK
    assert len(driver_calls) == 2   # inicial + re-run
    assert len(review_calls) == 2   # review após cada driver run


def test_run_queue_request_changes_persists_escalates(tmp_path: Path):
    """REQUEST_CHANGES persistente após max_retries → ESCALATE."""
    spec = _make_spec(tmp_path)
    log = _make_log()

    with (
        patch.object(queue_runner, "_run_driver", return_value=(True, "https://github.com/x/y/pull/99")),
        patch.object(queue_runner, "run_review", return_value={"verdict": "REQUEST_CHANGES", "findings": [], "proposed_tests": []}),
        patch.object(queue_runner, "_get_pr_changed_files", return_value=[]),
        patch.object(queue_runner, "_wait_for_ci", return_value=True),
        patch.object(queue_runner, "_merge_pr", return_value=True),
        patch.object(queue_runner, "_sync_base"),
        patch.object(queue_runner, "_save_proposed_tests"),
    ):
        result = queue_runner.run_queue([spec], _make_config(reviewer_max_retries=1), log)

    assert result == queue_runner.EXIT_REVIEWER_ESCALATED


def test_run_queue_security_risk_skips_reviewer(tmp_path: Path):
    """risk=security → EXIT_PAUSED_SECURITY sem chamar o revisor."""
    spec = _make_spec(tmp_path, risk="security")
    log = _make_log()
    review_mock = MagicMock()

    with (
        patch.object(queue_runner, "_run_driver", return_value=(True, "https://github.com/x/y/pull/5")),
        patch.object(queue_runner, "run_review", review_mock),
    ):
        result = queue_runner.run_queue([spec], _make_config(), log)

    assert result == queue_runner.EXIT_PAUSED_SECURITY
    review_mock.assert_not_called()
