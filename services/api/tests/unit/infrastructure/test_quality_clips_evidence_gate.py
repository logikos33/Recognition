"""
Tests: tasks/quality_clips.py — upload seletivo de evidência pro R2 (task-092,
ADR-0045 recorder-first, supersede ADR-0028 cloud-first).

Cobre:
- _tenant_id_for_schema: resolve tenant_id via public.tenants.schema_name;
  None se não encontrado ou erro de DB (nunca propaga).
- _should_upload_evidence_to_r2: ordem de decisão — flag explícita do tenant >
  deployment_mode de qualquer edge_site do tenant > fail-safe (mantém upload)
  quando tenant não resolvido, leitura falha, ou nenhum site 'edge' cadastrado.
- generate_quality_clip: quando o gate nega, NÃO baixa segmento nem chama
  ffmpeg/R2 — só marca clip_status='unavailable' e retorna cedo. Quando o
  gate permite, preserva o fluxo existente (regressão cloud_only).
- capture_reference_snapshot: mesma lógica — quando o gate nega, não abre
  RTSP nem sobe pro R2.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Mesmo guard usado em test_inference_auto_capture.py / test_quality_inference_onnx.py
# — evita stub de celery_app poluído por outro arquivo de teste.
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_QUALITY_CLIPS_KEY = "app.infrastructure.queue.tasks.quality_clips"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_QUALITY_CLIPS_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import quality_clips as qc_mod  # noqa: E402

_TENANT_SCHEMA = "tenant_rvb"
_TENANT_ID = str(uuid4())
_CAMERA_ID = str(uuid4())
_INSPECTION_ID = str(uuid4())


def _pool_with_cursor(mock_cursor: MagicMock) -> MagicMock:
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


class TestTenantIdForSchema:
    def test_resolves_tenant_id(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": _TENANT_ID}
        pool = _pool_with_cursor(cur)
        assert qc_mod._tenant_id_for_schema(pool, _TENANT_SCHEMA) == _TENANT_ID

    def test_returns_none_when_schema_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        pool = _pool_with_cursor(cur)
        assert qc_mod._tenant_id_for_schema(pool, _TENANT_SCHEMA) is None

    def test_returns_none_on_db_error_without_raising(self):
        pool = MagicMock()
        pool.get_connection.side_effect = RuntimeError("db down")
        assert qc_mod._tenant_id_for_schema(pool, _TENANT_SCHEMA) is None


class TestShouldUploadEvidenceToR2:
    def test_tenant_not_resolved_fails_safe_to_upload(self, monkeypatch):
        monkeypatch.setattr(qc_mod, "_tenant_id_for_schema", lambda pool, schema: None)
        assert qc_mod._should_upload_evidence_to_r2(MagicMock(), _TENANT_SCHEMA) is True

    def test_explicit_flag_true_overrides_edge_site(self, monkeypatch):
        monkeypatch.setattr(qc_mod, "_tenant_id_for_schema", lambda pool, schema: _TENANT_ID)
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository"
        ) as mock_flags_cls:
            mock_flags_cls.return_value.get_feature_flags.return_value = {
                "quality_evidence_r2_upload_enabled": True
            }
            result = qc_mod._should_upload_evidence_to_r2(MagicMock(), _TENANT_SCHEMA)
        assert result is True

    def test_explicit_flag_false_overrides_absence_of_edge_site(self, monkeypatch):
        monkeypatch.setattr(qc_mod, "_tenant_id_for_schema", lambda pool, schema: _TENANT_ID)
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository"
        ) as mock_flags_cls:
            mock_flags_cls.return_value.get_feature_flags.return_value = {
                "quality_evidence_r2_upload_enabled": False
            }
            result = qc_mod._should_upload_evidence_to_r2(MagicMock(), _TENANT_SCHEMA)
        assert result is False

    def test_flag_read_failure_falls_back_to_upload(self, monkeypatch):
        monkeypatch.setattr(qc_mod, "_tenant_id_for_schema", lambda pool, schema: _TENANT_ID)
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository",
            side_effect=RuntimeError("db down"),
        ):
            result = qc_mod._should_upload_evidence_to_r2(MagicMock(), _TENANT_SCHEMA)
        assert result is True

    def test_no_flag_and_edge_site_present_disables_upload(self, monkeypatch):
        monkeypatch.setattr(qc_mod, "_tenant_id_for_schema", lambda pool, schema: _TENANT_ID)
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository"
        ) as mock_flags_cls, patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository"
        ) as mock_site_cls:
            mock_flags_cls.return_value.get_feature_flags.return_value = {}
            mock_site_cls.return_value.list_sites.return_value = [
                {"id": "s1", "deployment_mode": "edge"}
            ]
            result = qc_mod._should_upload_evidence_to_r2(MagicMock(), _TENANT_SCHEMA)
        assert result is False

    def test_no_flag_and_only_cloud_sites_keeps_upload(self, monkeypatch):
        monkeypatch.setattr(qc_mod, "_tenant_id_for_schema", lambda pool, schema: _TENANT_ID)
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository"
        ) as mock_flags_cls, patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository"
        ) as mock_site_cls:
            mock_flags_cls.return_value.get_feature_flags.return_value = {}
            mock_site_cls.return_value.list_sites.return_value = [
                {"id": "s1", "deployment_mode": "cloud"}
            ]
            result = qc_mod._should_upload_evidence_to_r2(MagicMock(), _TENANT_SCHEMA)
        assert result is True

    def test_no_flag_and_no_sites_keeps_upload(self, monkeypatch):
        monkeypatch.setattr(qc_mod, "_tenant_id_for_schema", lambda pool, schema: _TENANT_ID)
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository"
        ) as mock_flags_cls, patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository"
        ) as mock_site_cls:
            mock_flags_cls.return_value.get_feature_flags.return_value = {}
            mock_site_cls.return_value.list_sites.return_value = []
            result = qc_mod._should_upload_evidence_to_r2(MagicMock(), _TENANT_SCHEMA)
        assert result is True

    def test_site_lookup_failure_falls_back_to_upload(self, monkeypatch):
        monkeypatch.setattr(qc_mod, "_tenant_id_for_schema", lambda pool, schema: _TENANT_ID)
        with patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository"
        ) as mock_flags_cls, patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository",
            side_effect=RuntimeError("db down"),
        ):
            mock_flags_cls.return_value.get_feature_flags.return_value = {}
            result = qc_mod._should_upload_evidence_to_r2(MagicMock(), _TENANT_SCHEMA)
        assert result is True


class TestGenerateQualityClipGate:
    def test_gate_denied_skips_download_and_marks_unavailable(self, monkeypatch):
        cur = MagicMock()
        pool = _pool_with_cursor(cur)
        monkeypatch.setattr(qc_mod, "_get_pool", lambda: pool)
        monkeypatch.setattr(qc_mod, "_should_upload_evidence_to_r2", lambda pool, schema: False)
        mock_storage = MagicMock()
        monkeypatch.setattr(qc_mod, "_get_storage", lambda: mock_storage)

        result = qc_mod.generate_quality_clip.apply(
            args=(_INSPECTION_ID, _CAMERA_ID, "2026-07-14T10:00:00+00:00", _TENANT_SCHEMA)
        ).get()

        assert result == {"status": "skipped_edge_recorder", "reason": "deployment_mode=edge"}
        mock_storage.download_bytes.assert_not_called()
        mock_storage.upload_bytes.assert_not_called()
        update_call = cur.execute.call_args_list[-1]
        assert "clip_status = 'unavailable'" in update_call.args[0]
        assert update_call.args[1] == (_INSPECTION_ID,)

    def test_gate_allowed_preserves_existing_no_segment_flow(self, monkeypatch):
        """Regressão cloud_only: gate=True não muda o comportamento existente
        (aqui, o caminho já coberto de 'segmento não encontrado')."""
        cur = MagicMock()
        # 1a query (buscar segmento) retorna None; 2a query é o UPDATE.
        cur.fetchone.return_value = None
        pool = _pool_with_cursor(cur)
        monkeypatch.setattr(qc_mod, "_get_pool", lambda: pool)
        monkeypatch.setattr(qc_mod, "_should_upload_evidence_to_r2", lambda pool, schema: True)
        mock_storage = MagicMock()
        monkeypatch.setattr(qc_mod, "_get_storage", lambda: mock_storage)

        result = qc_mod.generate_quality_clip.apply(
            args=(_INSPECTION_ID, _CAMERA_ID, "2026-07-14T10:00:00+00:00", _TENANT_SCHEMA)
        ).get()

        assert result == {"status": "unavailable", "reason": "no_segment_found"}
        mock_storage.download_bytes.assert_not_called()


class TestCaptureReferenceSnapshotGate:
    def test_gate_denied_skips_ffmpeg_and_upload(self, monkeypatch):
        pool = MagicMock()
        monkeypatch.setattr(qc_mod, "_get_pool", lambda: pool)
        monkeypatch.setattr(qc_mod, "_should_upload_evidence_to_r2", lambda pool, schema: False)
        mock_storage = MagicMock()
        monkeypatch.setattr(qc_mod, "_get_storage", lambda: mock_storage)

        with patch("subprocess.run") as mock_run:
            result = qc_mod.capture_reference_snapshot.apply(
                args=(_CAMERA_ID, _TENANT_SCHEMA, "ORDEM-1")
            ).get()

        assert result == {"status": "skipped_edge_recorder", "reason": "deployment_mode=edge"}
        mock_run.assert_not_called()
        mock_storage.upload_bytes.assert_not_called()

    def test_gate_allowed_proceeds_to_camera_lookup(self, monkeypatch):
        """Regressão cloud_only: gate=True chega até a etapa seguinte (busca
        RTSP), preservando o fluxo atual — aqui provado pela query executada."""
        cur = MagicMock()
        cur.fetchone.return_value = None  # câmera não encontrada -> status error
        pool = _pool_with_cursor(cur)
        monkeypatch.setattr(qc_mod, "_get_pool", lambda: pool)
        monkeypatch.setattr(qc_mod, "_should_upload_evidence_to_r2", lambda pool, schema: True)

        result = qc_mod.capture_reference_snapshot.apply(
            args=(_CAMERA_ID, _TENANT_SCHEMA, "ORDEM-1")
        ).get()

        assert result == {"status": "error"}
        assert cur.execute.call_args_list[-1].args[0] == (
            "SELECT rtsp_url FROM cameras WHERE id = %s"
        )
