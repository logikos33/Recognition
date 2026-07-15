"""
Tests: scripts/check_license_gate.py — scan de imports AGPL no código servido (task-081).

check_license_gate.py roda na raiz do repo (fora de services/api/) — importado
aqui via importlib a partir do path do arquivo, igual ao padrão usado em
training/vast/test_remote_train.py.

Falha-antes/passa-depois (ADR-0043): antes desta task, o gate só olhava
requirements.txt — um `from ultralytics import YOLO` direto num arquivo
servido passava despercebido. Depois, o AST-scan pega isso.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[4] / "scripts" / "check_license_gate.py"


def _load_gate_module():
    spec = importlib.util.spec_from_file_location("check_license_gate", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_license_gate"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


gate = _load_gate_module()


class TestImportedTopLevelPackages:
    def test_plain_import(self) -> None:
        assert gate._imported_top_level_packages("import ultralytics\n") == {"ultralytics"}

    def test_from_import(self) -> None:
        src = "from ultralytics import YOLO\n"
        assert gate._imported_top_level_packages(src) == {"ultralytics"}

    def test_submodule_import_resolves_top_level(self) -> None:
        assert gate._imported_top_level_packages("import ultralytics.utils\n") == {"ultralytics"}

    def test_relative_import_ignored(self) -> None:
        assert gate._imported_top_level_packages("from .base import Detector\n") == set()

    def test_unrelated_imports_not_flagged(self) -> None:
        src = "import onnxruntime\nfrom numpy import ndarray\n"
        assert gate._imported_top_level_packages(src) == {"onnxruntime", "numpy"}

    def test_syntax_error_returns_empty_not_raise(self) -> None:
        assert gate._imported_top_level_packages("def broken(:\n") == set()


class TestCheckSourceImports:
    def test_current_repo_passes_baseline(self) -> None:
        """Estado atual do repo (com KNOWN_IMPORT_EXCEPTIONS) não deve violar o gate."""
        root = _MODULE_PATH.parent.parent
        violations = gate._check_source_imports(root)
        assert violations == [], f"violações inesperadas: {violations}"

    def test_new_agpl_import_in_serving_path_is_caught(self, tmp_path) -> None:
        """Introduzir `import ultralytics` num arquivo NÃO listado em
        KNOWN_IMPORT_EXCEPTIONS faz o gate falhar — o caso que motivou a task-081."""
        served_dir = tmp_path / "services" / "api" / "app" / "domain" / "detectors"
        served_dir.mkdir(parents=True)
        violating_file = served_dir / "new_bad_detector.py"
        violating_file.write_text("from ultralytics import YOLO\n")

        violations = gate._check_source_imports(tmp_path)

        assert len(violations) == 1
        path, reason = violations[0]
        assert path == violating_file
        assert "ultralytics" in reason

    def test_known_exception_file_is_skipped(self, tmp_path, monkeypatch) -> None:
        """Arquivo listado em KNOWN_IMPORT_EXCEPTIONS não bloqueia o gate
        (dívida documentada, amarrada a uma task de remoção).

        A allowlist real está VAZIA desde a task-080 — o mecanismo continua
        coberto via monkeypatch para o dia em que uma nova dívida datada
        precisar entrar (com task de remoção associada)."""
        rel = "services/api/app/domain/detectors/hypothetical_debt.py"
        monkeypatch.setattr(gate, "KNOWN_IMPORT_EXCEPTIONS", frozenset({rel}))
        exception_path = tmp_path / rel
        exception_path.parent.mkdir(parents=True, exist_ok=True)
        exception_path.write_text("from ultralytics import YOLO\n")

        violations = gate._check_source_imports(tmp_path)

        assert violations == []

    def test_allowlist_esta_vazia_desde_task_080(self) -> None:
        """AGPL-zero pleno (ADR-0043): o baseline de exceções da task-081 foi
        zerado por task-079 (quality) + task-080 (compat shim do EPI). Se este
        teste falhar porque alguém adicionou uma entrada, exija a task de
        remoção associada no comentário da entrada."""
        assert gate.KNOWN_IMPORT_EXCEPTIONS == frozenset()

    def test_known_import_exceptions_all_still_exist_and_import_ultralytics(self) -> None:
        """Guarda contra allowlist obsoleta: cada exceção listada precisa
        continuar existindo e violando de fato — senão é hora de removê-la."""
        root = _MODULE_PATH.parent.parent
        for rel in gate.KNOWN_IMPORT_EXCEPTIONS:
            path = root / rel
            assert path.exists(), f"exceção obsoleta (arquivo não existe mais): {rel}"
            packages = gate._imported_top_level_packages(path.read_text())
            assert packages & gate.AGPL_PACKAGES, f"exceção obsoleta (sem import AGPL): {rel}"


class TestMainExitCode:
    def test_main_passes_on_current_repo(self, capsys) -> None:
        assert gate.main() == 0
        assert "PASSED" in capsys.readouterr().out
