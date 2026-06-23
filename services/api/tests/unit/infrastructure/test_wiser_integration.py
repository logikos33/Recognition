"""Tests: wiser_integration.py — WiserIntegration, _get_filename_base,
_export_file_share, _export_api, _export_pdf, export_piece, get_wiser_integration."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch



# ---------------------------------------------------------------------------
# Module-level setup: stub reportlab so the import doesn't crash the suite
# ---------------------------------------------------------------------------
if "reportlab" not in sys.modules:
    _rl_stub = MagicMock()
    sys.modules["reportlab"] = _rl_stub
    sys.modules["reportlab.lib"] = _rl_stub
    sys.modules["reportlab.lib.pagesizes"] = _rl_stub
    sys.modules["reportlab.lib.styles"] = _rl_stub
    sys.modules["reportlab.platypus"] = _rl_stub


def _make_wi():
    """Return a fresh WiserIntegration instance."""
    from app.api.v1.quality.wiser_integration import WiserIntegration
    return WiserIntegration()


# ---------------------------------------------------------------------------
# _get_filename_base
# ---------------------------------------------------------------------------

class TestGetFilenameBase:

    def test_standard_piece_format(self):
        wi = _make_wi()
        piece = {"work_order": "OP1234", "piece_number": "PC5678", "status": "approved"}
        base = wi._get_filename_base(piece)
        assert base.startswith("OP1234_PC5678_APPROVED_")

    def test_status_is_uppercased(self):
        wi = _make_wi()
        base = wi._get_filename_base({"work_order": "OP01", "piece_number": "P01", "status": "approved"})
        assert "_APPROVED_" in base

    def test_slash_in_work_order_replaced_with_dash(self):
        wi = _make_wi()
        base = wi._get_filename_base({"work_order": "OP/2024", "piece_number": "P1", "status": "approved"})
        assert "/" not in base
        assert "OP-2024" in base

    def test_slash_in_piece_number_replaced_with_dash(self):
        wi = _make_wi()
        base = wi._get_filename_base({"work_order": "OP1", "piece_number": "P/1", "status": "approved"})
        assert "/" not in base
        assert "P-1" in base

    def test_missing_work_order_uses_semop(self):
        wi = _make_wi()
        base = wi._get_filename_base({"piece_number": "P1", "status": "approved"})
        assert base.startswith("SEMOP_")

    def test_missing_piece_number_uses_semnum(self):
        wi = _make_wi()
        base = wi._get_filename_base({"work_order": "OP1", "status": "approved"})
        assert "_SEMNUM_" in base

    def test_missing_status_defaults_to_approved(self):
        wi = _make_wi()
        base = wi._get_filename_base({"work_order": "OP1", "piece_number": "P1"})
        assert "_APPROVED_" in base

    def test_timestamp_portion_has_correct_length(self):
        wi = _make_wi()
        base = wi._get_filename_base({"work_order": "OP1", "piece_number": "P1", "status": "approved"})
        # Format: OP1_P1_APPROVED_YYYYMMDD_HHMMSS
        parts = base.split("_")
        # last two parts are date and time
        assert len(parts[-2]) == 8   # YYYYMMDD
        assert len(parts[-1]) == 6   # HHMMSS


# ---------------------------------------------------------------------------
# _export_file_share
# ---------------------------------------------------------------------------

class TestExportFileShare:

    def test_creates_json_file(self, tmp_path):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved",
                 "product_type": "widget", "total_rework_count": 0}
        with patch.object(wi_mod, "WISER_FILE_SHARE_PATH", str(tmp_path)):
            result = wi._export_file_share(piece, "")
        assert result["success"] is True
        assert result["method"] == "file_share"
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 1
        data = json.loads(json_files[0].read_text())
        assert data["work_order"] == "OP1"

    def test_copies_photo_when_exists(self, tmp_path):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        photo = tmp_path / "photo.jpg"
        photo.write_bytes(b"fake-jpeg")
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        export_dir = tmp_path / "export"
        with patch.object(wi_mod, "WISER_FILE_SHARE_PATH", str(export_dir)):
            result = wi._export_file_share(piece, str(photo))
        assert result["success"] is True
        jpg_files = list(export_dir.glob("*.jpg"))
        assert len(jpg_files) == 1

    def test_succeeds_without_photo(self, tmp_path):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        with patch.object(wi_mod, "WISER_FILE_SHARE_PATH", str(tmp_path)):
            result = wi._export_file_share(piece, "")
        assert result["success"] is True

    def test_returns_failure_on_os_error(self, tmp_path):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        with patch.object(wi_mod, "WISER_FILE_SHARE_PATH", str(tmp_path)), \
             patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            result = wi._export_file_share(piece, "")
        assert result["success"] is False
        assert result["method"] == "file_share"
        assert "disk full" in result["error"]

    def test_result_path_points_to_json_file(self, tmp_path):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        with patch.object(wi_mod, "WISER_FILE_SHARE_PATH", str(tmp_path)):
            result = wi._export_file_share(piece, "")
        assert result["path"].endswith(".json")
        assert Path(result["path"]).exists()


# ---------------------------------------------------------------------------
# _export_api
# ---------------------------------------------------------------------------

class TestExportApi:

    def test_success_returns_success_true(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        mock_requests = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_resp
        piece = {"piece_number": "P1", "work_order": "OP1", "status": "approved"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local:8080"), \
             patch.dict(sys.modules, {"requests": mock_requests}):
            result = wi._export_api(piece, "")
        assert result["success"] is True
        assert result["method"] == "api"

    def test_raises_for_status_on_error_returns_failure(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        mock_requests = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        mock_requests.post.return_value = mock_resp
        piece = {"piece_number": "P1"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local:8080"), \
             patch.dict(sys.modules, {"requests": mock_requests}):
            result = wi._export_api(piece, "")
        assert result["success"] is False
        assert "500 Server Error" in result["error"]

    def test_exception_during_post_returns_failure(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        mock_requests = MagicMock()
        mock_requests.post.side_effect = Exception("connection refused")
        piece = {"piece_number": "P1"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local:8080"), \
             patch.dict(sys.modules, {"requests": mock_requests}):
            result = wi._export_api(piece, "")
        assert result["success"] is False
        assert result["method"] == "api"

    def test_posts_to_quality_pieces_endpoint(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        mock_requests = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_resp
        piece = {"piece_number": "P1"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local"), \
             patch.dict(sys.modules, {"requests": mock_requests}):
            wi._export_api(piece, "")
        url_called = mock_requests.post.call_args[0][0]
        assert url_called == "http://wiser.local/quality/pieces"

    def test_sends_metadata_as_json_string(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        mock_requests = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_resp
        piece = {"piece_number": "P-99", "work_order": "OP-99", "status": "approved"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local"), \
             patch.dict(sys.modules, {"requests": mock_requests}):
            wi._export_api(piece, "")
        data_arg = mock_requests.post.call_args[1]["data"]
        metadata = json.loads(data_arg["metadata"])
        assert metadata["piece_number"] == "P-99"


# ---------------------------------------------------------------------------
# _export_pdf — reportlab not installed → ImportError → success=False
# ---------------------------------------------------------------------------

class TestExportPdf:

    def test_returns_failure_when_reportlab_unavailable(self):
        wi = _make_wi()
        broken_rl = MagicMock()
        # Make importing from reportlab.platypus raise ImportError
        broken_rl.platypus = MagicMock()
        broken_rl.platypus.SimpleDocTemplate = None

        # Force the import inside _export_pdf to fail
        with patch.dict(sys.modules, {
            "reportlab": None,
            "reportlab.lib": None,
            "reportlab.lib.pagesizes": None,
            "reportlab.lib.styles": None,
            "reportlab.platypus": None,
        }):
            result = wi._export_pdf({"piece_number": "P1"}, "")
        assert result["success"] is False
        assert result["method"] == "pdf"

    def test_returns_failure_with_error_string(self):
        wi = _make_wi()
        with patch.dict(sys.modules, {
            "reportlab": None,
            "reportlab.lib": None,
            "reportlab.lib.pagesizes": None,
            "reportlab.lib.styles": None,
            "reportlab.platypus": None,
        }):
            result = wi._export_pdf({}, "")
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0


# ---------------------------------------------------------------------------
# export_piece — integration (fallback chain)
# ---------------------------------------------------------------------------

class TestExportPiece:

    def test_uses_file_share_when_no_api_url(self, tmp_path):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        with patch.object(wi_mod, "WISER_API_URL", ""), \
             patch.object(wi_mod, "WISER_FILE_SHARE_PATH", str(tmp_path)):
            result = wi.export_piece(piece, "")
        assert result["method"] == "file_share"
        assert result["success"] is True

    def test_uses_api_when_url_configured_and_api_succeeds(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local"), \
             patch.object(wi, "_export_api", return_value={"success": True, "method": "api",
                                                            "path": "http://wiser.local", "error": ""}):
            result = wi.export_piece(piece, "")
        assert result["method"] == "api"

    def test_falls_back_to_file_share_when_api_fails(self, tmp_path):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local"), \
             patch.object(wi, "_export_api", return_value={"success": False, "method": "api",
                                                            "path": "", "error": "timeout"}), \
             patch.object(wi_mod, "WISER_FILE_SHARE_PATH", str(tmp_path)):
            result = wi.export_piece(piece, "")
        assert result["method"] == "file_share"
        assert result["success"] is True

    def test_falls_back_to_pdf_when_both_api_and_file_share_fail(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local"), \
             patch.object(wi, "_export_api", return_value={"success": False, "method": "api",
                                                            "path": "", "error": "fail"}), \
             patch.object(wi, "_export_file_share", return_value={"success": False, "method": "file_share",
                                                                    "path": "", "error": "no network"}), \
             patch.object(wi, "_export_pdf", return_value={"success": False, "method": "pdf",
                                                            "path": "", "error": "no reportlab"}) as mock_pdf:
            result = wi.export_piece(piece, "")
        mock_pdf.assert_called_once()
        assert result["method"] == "pdf"

    def test_does_not_call_file_share_when_api_succeeds(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi = _make_wi()
        piece = {"work_order": "OP1", "piece_number": "P1", "status": "approved"}
        with patch.object(wi_mod, "WISER_API_URL", "http://wiser.local"), \
             patch.object(wi, "_export_api", return_value={"success": True, "method": "api",
                                                            "path": "http://wiser.local", "error": ""}), \
             patch.object(wi, "_export_file_share") as mock_fs:
            wi.export_piece(piece, "")
        mock_fs.assert_not_called()


# ---------------------------------------------------------------------------
# get_wiser_integration — singleton
# ---------------------------------------------------------------------------

class TestGetWiserIntegration:

    def test_returns_wiser_integration_instance(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi_mod._wiser = None
        from app.api.v1.quality.wiser_integration import WiserIntegration, get_wiser_integration
        result = get_wiser_integration()
        assert isinstance(result, WiserIntegration)

    def test_returns_same_instance_on_repeated_calls(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi_mod._wiser = None
        from app.api.v1.quality.wiser_integration import get_wiser_integration
        a = get_wiser_integration()
        b = get_wiser_integration()
        assert a is b

    def test_singleton_can_be_reset_for_testing(self):
        import app.api.v1.quality.wiser_integration as wi_mod
        wi_mod._wiser = None
        from app.api.v1.quality.wiser_integration import get_wiser_integration
        a = get_wiser_integration()
        wi_mod._wiser = None
        b = get_wiser_integration()
        assert a is not b
