"""
Tests: tasks/quality_training.py — treino real desativado (task-079,
ADR-0043 AGPL-zero).

O pipeline treinava localmente com `from ultralytics import YOLO` (AGPL-3.0)
dentro do worker Celery servido — proibido pelo ADR-0043. O treino real via
ONNX/RF-DETR (Apache) é escopo da task-086 (ainda não implementada). Este
módulo cobre a desativação explícita e não-silenciosa (ADR-0017):
- Dataset ainda é montado (coleta + conversão de anotações para YOLO).
- Etapa de treino falha explicitamente: status="failed" no banco,
  reason="training_pending_task_086" no retorno da task — nunca finge sucesso
  nem tenta importar ultralytics.
"""
from __future__ import annotations

import inspect
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_QUALITY_TRAINING_KEY = "app.infrastructure.queue.tasks.quality_training"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_QUALITY_TRAINING_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import quality_training as qt_mod  # noqa: E402

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TENANT_SCHEMA = "tenant_rvb"


class TestNoUltralyticsImport:
    def test_module_source_has_no_ultralytics_import(self):
        # Via AST (não substring) — o módulo MENCIONA "ultralytics" em
        # comentários/docstrings explicando a desativação; o que importa é
        # que nenhum nó Import/ImportFrom real referencie o pacote.
        import ast
        tree = ast.parse(inspect.getsource(qt_mod))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(a.name.startswith("ultralytics") for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("ultralytics")
        assert "YOLO(" not in inspect.getsource(qt_mod)

    def test_ultralytics_de_fato_nao_esta_instalado_neste_venv(self):
        """Fail-antes/passa-depois: antes desta mudança,
        run_quality_training_pipeline chamava `from ultralytics import YOLO`
        e ImportError-ava neste venv de CI (sem ultralytics — AGPL, fora de
        requirements/*.txt). Depois, a task nunca tenta importar ultralytics
        — falha explicitamente antes disso (ver testes abaixo)."""
        with pytest.raises(ModuleNotFoundError):
            import ultralytics  # noqa: F401


def _frame_row(i: int) -> dict:
    return {
        "id": f"frame-{i}",
        "r2_key": f"quality-frames/{_TENANT_SCHEMA}/{i}.jpg",
        "annotations": json.dumps(
            [{"class_id": 1, "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.2}]
        ),
        "inspection_id": f"insp-{i}",
    }


def _make_pool(job_row: dict | None, frame_rows: list[dict]):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = job_row
    cur.fetchall.return_value = frame_rows

    conn_cm = MagicMock()
    conn_cm.__enter__.return_value = conn
    conn_cm.__exit__.return_value = False

    pool = MagicMock()
    pool.get_connection.return_value = conn_cm
    return pool


class TestRunQualityTrainingPipelineDisabled:
    def test_monta_dataset_mas_falha_explicitamente_na_etapa_de_treino(self):
        job_row = {"id": _JOB_ID, "status": "queued"}
        frame_rows = [_frame_row(i) for i in range(12)]  # >= 10 (mínimo válido)
        pool = _make_pool(job_row, frame_rows)

        storage = MagicMock()
        storage.download_bytes.return_value = b"\xff\xd8\xff\xe0fake-jpeg-bytes"

        with patch.object(qt_mod, "_get_pool", return_value=pool), patch.object(
            qt_mod, "_get_storage", return_value=storage
        ), patch.object(qt_mod, "_get_redis", return_value=MagicMock()), patch.object(
            qt_mod, "_update_job_status"
        ) as mock_update_status, patch.object(
            qt_mod, "_publish_progress"
        ) as mock_publish:
            # tmp_dir real sob /tmp/quality_training/{job_id} — mesmo
            # comportamento de produção; a própria task limpa via
            # shutil.rmtree no finally.
            result = qt_mod.run_quality_training_pipeline.apply(
                args=(_JOB_ID, _TENANT_SCHEMA)
            ).get()

        assert result["status"] == "error"
        assert result["reason"] == "training_pending_task_086"
        assert result["job_id"] == _JOB_ID

        # Job marcado 'failed' de forma explícita — nunca 'completed' fake.
        failed_calls = [
            c for c in mock_update_status.call_args_list
            if c.args[2] == "failed"
        ]
        assert failed_calls, "esperava _update_job_status(..., 'failed', ...)"
        assert "task-086" in failed_calls[-1].kwargs.get("error_message", "")

        # Progresso final é um evento de erro, não de sucesso.
        error_progress = [
            c for c in mock_publish.call_args_list if c.args[1] == "error"
        ]
        assert error_progress

    def test_job_inexistente_retorna_erro_sem_tentar_treinar(self):
        pool = _make_pool(job_row=None, frame_rows=[])

        with patch.object(qt_mod, "_get_pool", return_value=pool), patch.object(
            qt_mod, "_get_redis", return_value=MagicMock()
        ):
            result = qt_mod.run_quality_training_pipeline.apply(
                args=(_JOB_ID, _TENANT_SCHEMA)
            ).get()

        assert result == {"status": "error", "reason": "job_not_found"}
