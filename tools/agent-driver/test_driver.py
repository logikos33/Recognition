"""Testes leves do driver — sem subprocess real, sem claude, sem docker.

Garante que os trilhos de segurança estão no lugar:
  - protected_branches inclui main/develop/staging (defense-in-depth)
  - base_branch existe e é configurável
  - --model é passado pro claude (model routing acontece)
  - git add/commit fora da allowlist (driver faz, não o claude)
"""

import inspect
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import driver  # noqa: E402


def test_protected_branches_include_main_develop_staging():
    config = driver._load_config()
    protected = config["guard_rails"]["protected_branches"]
    for branch in ("main", "develop", "staging"):
        assert branch in protected, f"branch '{branch}' deve estar em protected_branches"


def test_base_branch_is_configured():
    config = driver._load_config()
    assert "base_branch" in config, "config.yaml deve ter base_branch"
    assert config["base_branch"], "base_branch não pode ser vazio"


def test_claude_cmd_includes_model_flag():
    config = driver._load_config()
    cmd = driver._build_claude_cmd("prompt qualquer", config["model"], config["allowed_tools"])
    assert "--model" in cmd, "comando do claude deve incluir --model"
    idx = cmd.index("--model")
    assert cmd[idx + 1] == config["model"], "valor de --model deve vir do config"


def test_allowlist_excludes_git_add_and_commit():
    config = driver._load_config()
    tools = config["allowed_tools"]
    for forbidden in ("Bash(git add:*)", "Bash(git commit:*)"):
        assert forbidden not in tools, (
            f"{forbidden} não pode estar na allowlist — driver faz commits, claude só edita"
        )


def test_allowlist_keeps_readonly_git():
    """Sanidade: leituras de git pra contexto continuam permitidas."""
    config = driver._load_config()
    tools = config["allowed_tools"]
    for required in (
        "Bash(git status)",
        "Bash(git diff:*)",
        "Bash(git log:*)",
        "Bash(git ls-files:*)",
    ):
        assert required in tools, f"{required} deve estar na allowlist (leitura de contexto)"


def test_work_branch_name_uses_agent_prefix():
    spec = Path("tools/agent-driver/tasks/task-001-harness-final-state-assert.md")
    name = driver._make_work_branch_name(spec)
    assert name.startswith("agent/"), "branch de trabalho deve ter prefixo agent/"
    assert "task-001-harness-final-state-assert" in name, "nome deve incluir o stem da spec"


def test_dangerous_flag_not_in_claude_cmd():
    """--dangerously-skip-permissions JAMAIS deve aparecer no cmd."""
    config = driver._load_config()
    cmd = driver._build_claude_cmd("p", config["model"], config["allowed_tools"])
    assert "--dangerously-skip-permissions" not in cmd


# ---------------------------------------------------------------------------
# _is_tree_dirty — função pura, sem subprocess
# ---------------------------------------------------------------------------


def test_is_tree_dirty_empty_is_clean():
    assert driver._is_tree_dirty([]) is False


def test_is_tree_dirty_untracked_is_dirty():
    assert driver._is_tree_dirty(["?? docs/novo.md"]) is True


def test_is_tree_dirty_modified_tracked_is_dirty():
    assert driver._is_tree_dirty([" M arquivo.py"]) is True


def test_is_tree_dirty_staged_is_dirty():
    assert driver._is_tree_dirty(["A  staged.py"]) is True


def test_is_tree_dirty_blank_lines_only_is_clean():
    assert driver._is_tree_dirty(["", "  ", "\t"]) is False


# ---------------------------------------------------------------------------
# run_implementer_retry — API + garantias de não-escrita e não-assert-clean-tree
# ---------------------------------------------------------------------------


def test_run_implementer_retry_exists_with_expected_params():
    """run_implementer_retry deve existir e aceitar os parâmetros corretos."""
    assert hasattr(driver, "run_implementer_retry")
    sig = inspect.signature(driver.run_implementer_retry)
    for param in ("spec_path", "spec_body", "eval_name", "review_feedback", "config", "log"):
        assert param in sig.parameters, f"parâmetro '{param}' ausente em run_implementer_retry"


def test_run_implementer_retry_does_not_assert_clean_tree():
    """run_implementer_retry NÃO pode chamar _assert_clean_tree — evita exit 7 auto-induzido."""
    source = inspect.getsource(driver.run_implementer_retry)
    assert "_assert_clean_tree" not in source


def test_run_implementer_retry_writes_no_files():
    """run_implementer_retry não usa write_text/write — não suja o working tree."""
    source = inspect.getsource(driver.run_implementer_retry)
    assert ".write_text" not in source
    assert ".write(" not in source


def test_commit_retry_on_branch_exists():
    """commit_retry_on_branch deve existir como função pública."""
    assert hasattr(driver, "commit_retry_on_branch")
    assert callable(driver.commit_retry_on_branch)


# ---------------------------------------------------------------------------
# _commit_and_pr — staging escopado (sem git add -A)
# ---------------------------------------------------------------------------


def test_commit_and_pr_no_git_add_all_in_source():
    """_commit_and_pr NÃO deve usar 'git add -A' — staging escopado obrigatório."""
    source = inspect.getsource(driver._commit_and_pr)
    assert '"-A"' not in source, "_commit_and_pr contém git add -A; usar staging escopado"


def test_commit_and_pr_excludes_planted_untracked_file():
    """Arquivo untracked plantado fora de runs/ NÃO entra no staging quando _changed_files
    retorna apenas os arquivos do agente.
    """
    agent_files = ["tools/agent-driver/driver.py"]
    planted_file = "tools/agent-driver/temp_leaked.md"
    log = logging.getLogger("test_commit")
    meta = {"title": "T", "commit_message": "feat: T"}

    git_add_calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        if isinstance(cmd, list) and len(cmd) >= 2 and cmd[:2] == ["git", "add"]:
            git_add_calls.append(list(cmd))
        mock = MagicMock()
        # git diff --cached --quiet: returncode=1 significa "há staged changes"
        mock.returncode = 1 if (isinstance(cmd, list) and "--cached" in cmd) else 0
        mock.stdout = "https://github.com/x/y/pull/1\n"
        mock.stderr = ""
        return mock

    with patch.object(driver, "_current_branch", return_value="agent/task-001"), \
         patch.object(driver, "_changed_files", return_value=agent_files), \
         patch("subprocess.run", side_effect=fake_run):
        driver._commit_and_pr(meta, "develop", log)

    # planted_file NÃO deve estar em nenhuma chamada de git add
    for cmd in git_add_calls:
        assert planted_file not in cmd, f"Arquivo plantado encontrado em git add: {cmd}"

    # git add -A NÃO deve ter sido chamado
    for cmd in git_add_calls:
        assert "-A" not in cmd, f"git add -A foi chamado: {cmd}"

    # git add -- <agent_files> DEVE ter sido chamado
    assert any(
        "--" in cmd and agent_files[0] in cmd for cmd in git_add_calls
    ), "git add -- <agent_files> não foi chamado"
