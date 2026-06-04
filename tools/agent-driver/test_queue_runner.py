"""Testes do queue_runner — sem subprocess real, sem gh, sem driver (tudo mockado).

Invariantes verificadas:
  - _parse_risk: com e sem campo risk; fail-safe = security [crítico]
  - _should_auto_merge: low + success + develop → True; demais → False
  - NUNCA decide mergear se base != develop
  - _parse_pr_number: extrai corretamente de URL do gh
"""

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
