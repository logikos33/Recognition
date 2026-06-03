"""Testes leves do driver — sem subprocess real, sem claude, sem docker.

Garante que os trilhos de segurança estão no lugar:
  - protected_branches inclui main/develop/staging (defense-in-depth)
  - base_branch existe e é configurável
  - --model é passado pro claude (model routing acontece)
  - git add/commit fora da allowlist (driver faz, não o claude)
"""

import sys
from pathlib import Path

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
