"""
Testes unitarios para WiserIntegration.
"""
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.quality.wiser_integration import WiserIntegration


PIECE = {
    "piece_number": "12345",
    "work_order": "OP001",
    "product_type": "Produto A",
    "status": "approved",
    "total_rework_count": 0,
    "total_rework_time_seconds": 0,
}
PHOTO_PATH = "/tmp/fake_photo.jpg"


@pytest.fixture
def integration():
    return WiserIntegration()


def test_export_api_success(integration):
    """_export_api deve retornar success=True quando POST retorna 200."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_requests = MagicMock()
    mock_requests.post.return_value = mock_resp

    with patch.dict(os.environ, {"WISER_API_URL": "http://wiser.local:8080"}), \
         patch.dict("sys.modules", {"requests": mock_requests}), \
         patch("os.path.exists", return_value=False):
        result = integration._export_api(PIECE, PHOTO_PATH)

    assert result["success"] is True
    assert result["method"] == "api"


def test_export_api_fails_fallback_file_share(integration):
    """export_piece deve tentar file_share quando API falha."""
    mock_requests = MagicMock()
    mock_requests.post.side_effect = Exception("connection refused")

    with patch.dict(os.environ, {
        "WISER_API_URL": "http://wiser.local:8080",
        "WISER_FILE_SHARE_PATH": "/tmp/wiser_test_export",
    }), patch.dict("sys.modules", {"requests": mock_requests}), \
         patch("os.path.exists", return_value=False), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_text"):
        result = integration.export_piece(PIECE, PHOTO_PATH)

    # Deve ter tentado file_share ou pdf apos API falhar
    assert result["method"] in ("file_share", "pdf")


def test_export_file_share_writes_json_file(integration, tmp_path):
    """_export_file_share deve criar arquivo JSON com metadados da peca."""
    # WISER_FILE_SHARE_PATH e lido em tempo de import como variavel de modulo,
    # portanto precisamos patchear a variavel de modulo diretamente.
    with patch("app.api.v1.quality.wiser_integration.WISER_FILE_SHARE_PATH", str(tmp_path)), \
         patch("os.path.exists", return_value=False):
        result = integration._export_file_share(PIECE, PHOTO_PATH)

    assert result["success"] is True
    assert result["method"] == "file_share"
    # Verifica que arquivo JSON foi criado
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1
    data = json.loads(json_files[0].read_text())
    assert data["piece_number"] == "12345"


def test_export_pdf_creates_file(integration, tmp_path):
    """_export_pdf deve criar arquivo PDF quando reportlab disponivel."""
    pytest.importorskip("reportlab", reason="reportlab nao instalado")

    with patch("app.api.v1.quality.wiser_integration.WISER_PDF_DIR", str(tmp_path)):
        result = integration._export_pdf(PIECE, PHOTO_PATH)

    assert result["success"] is True
    assert result["method"] == "pdf"
    assert result["error"] == ""
    assert os.path.isfile(result["path"]), f"PDF not created at {result['path']}"


def test_export_all_fail_returns_error(integration):
    """export_piece deve retornar success=False quando todos os modos falham."""
    with patch.dict(os.environ, {
        "WISER_API_URL": "",
        "WISER_FILE_SHARE_PATH": "/nonexistent/path/that/cannot/be/created",
        "WISER_PDF_DIR": "/nonexistent/path/that/cannot/be/created",
    }), patch("pathlib.Path.mkdir", side_effect=PermissionError("sem permissao")):
        result = integration.export_piece(PIECE, PHOTO_PATH)

    assert result["success"] is False
