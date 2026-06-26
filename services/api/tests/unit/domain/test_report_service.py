"""
Tests: ReportService.get_home_reports + helper factories _get_alert_repo/_get_camera_repo.

Repo factory functions are patched at module level so no real DB is needed.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.domain.services.report_service import ReportService, _get_alert_repo, _get_camera_repo

_POOL_PATH = "app.domain.services.report_service.DatabasePool"
_GET_ALERT = "app.domain.services.report_service._get_alert_repo"
_GET_CAMERA = "app.domain.services.report_service._get_camera_repo"


def _service() -> ReportService:
    return ReportService()


def _mock_alert_repo(today=5, week=20, by_hour=None):
    repo = MagicMock()
    repo.count_all_since.side_effect = [today, week]
    repo.count_by_hour.return_value = by_hour or []
    return repo


def _mock_camera_repo(active=3, total=5):
    repo = MagicMock()
    repo.count_active_all.return_value = active
    repo.count_all.return_value = total
    return repo


# ---------------------------------------------------------------------------
# _get_alert_repo
# ---------------------------------------------------------------------------

class TestGetAlertRepo:

    def test_pool_none_raises_runtime_error(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="Database pool"):
                _get_alert_repo()

    def test_returns_alert_repository_with_pool(self):
        from app.infrastructure.database.repositories.alert_repository import AlertRepository
        mock_pool = MagicMock()
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            result = _get_alert_repo()
        assert isinstance(result, AlertRepository)


# ---------------------------------------------------------------------------
# _get_camera_repo
# ---------------------------------------------------------------------------

class TestGetCameraRepo:

    def test_pool_none_raises_runtime_error(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="Database pool"):
                _get_camera_repo()

    def test_returns_camera_repository_with_pool(self):
        from app.infrastructure.database.repositories.camera_repository import CameraRepository
        mock_pool = MagicMock()
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            result = _get_camera_repo()
        assert isinstance(result, CameraRepository)


# ---------------------------------------------------------------------------
# get_home_reports
# ---------------------------------------------------------------------------

class TestGetHomeReports:

    def _call(self, alert_repo=None, camera_repo=None, tenant_id="tenant-1"):
        a = alert_repo or _mock_alert_repo()
        c = camera_repo or _mock_camera_repo()
        with patch(_GET_ALERT, return_value=a), patch(_GET_CAMERA, return_value=c):
            return _service().get_home_reports(tenant_id)

    def test_returns_cards_and_chart_keys(self):
        result = self._call()
        assert "cards" in result
        assert "chart" in result

    def test_cards_has_expected_keys(self):
        result = self._call()
        cards = result["cards"]
        for key in ("alerts_today", "alerts_week", "cameras_active",
                    "cameras_total", "processings_today", "objects_identified"):
            assert key in cards

    def test_alerts_today_from_first_repo_call(self):
        result = self._call(alert_repo=_mock_alert_repo(today=7, week=42))
        assert result["cards"]["alerts_today"] == 7

    def test_alerts_week_from_second_repo_call(self):
        result = self._call(alert_repo=_mock_alert_repo(today=0, week=42))
        assert result["cards"]["alerts_week"] == 42

    def test_cameras_active_from_repo(self):
        result = self._call(camera_repo=_mock_camera_repo(active=4, total=6))
        assert result["cards"]["cameras_active"] == 4

    def test_cameras_total_from_repo(self):
        result = self._call(camera_repo=_mock_camera_repo(active=1, total=10))
        assert result["cards"]["cameras_total"] == 10

    def test_processings_today_estimate(self):
        result = self._call(camera_repo=_mock_camera_repo(active=2))
        # 2 cameras * 3600 frames/h * 8h
        assert result["cards"]["processings_today"] == 2 * 3600 * 8

    def test_objects_identified_is_3x_processings(self):
        result = self._call(camera_repo=_mock_camera_repo(active=3))
        p = result["cards"]["processings_today"]
        assert result["cards"]["objects_identified"] == p * 3

    def test_chart_alerts_by_hour_empty(self):
        result = self._call(alert_repo=_mock_alert_repo(by_hour=[]))
        assert result["chart"]["alerts_by_hour"] == []

    def test_chart_alerts_by_hour_mapped(self):
        import datetime
        hour_val = datetime.datetime(2026, 1, 1, 15, 0, 0)
        alert_repo = _mock_alert_repo(by_hour=[{"hour": hour_val, "count": 12}])
        result = self._call(alert_repo=alert_repo)
        row = result["chart"]["alerts_by_hour"][0]
        assert row["count"] == 12
        assert str(hour_val) in row["hour"]

    def test_tenant_id_forwarded_to_repos(self):
        alert_repo = _mock_alert_repo()
        camera_repo = _mock_camera_repo()
        with patch(_GET_ALERT, return_value=alert_repo), \
             patch(_GET_CAMERA, return_value=camera_repo):
            _service().get_home_reports("tid-99")
        # both repos should have received "tid-99" as tenant_id
        for call in alert_repo.count_all_since.call_args_list:
            assert call[0][0] == "tid-99"
        camera_repo.count_active_all.assert_called_once_with("tid-99")
        camera_repo.count_all.assert_called_once_with("tid-99")

    def test_zero_cameras_gives_zero_processings(self):
        result = self._call(camera_repo=_mock_camera_repo(active=0))
        assert result["cards"]["processings_today"] == 0
        assert result["cards"]["objects_identified"] == 0
