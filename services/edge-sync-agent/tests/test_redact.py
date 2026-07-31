"""Tests: redação de credencial antes de qualquer log/mensagem de erro.

Vazamento real no DEV (2026-07-31): o stderr do ffmpeg era logado cru e
despejava a senha do gravador do cliente em texto puro no log do Railway:

    ffmpeg_stderr: ... Error opening input file rtsp://Admin:<SENHA>@192.168.35.18:554/...
"""
from app.redact import redact_bytes, redact_url_credentials

SENHA = "S3nh4Sup3rS3cr3t4"


def test_rtsp_password_is_redacted():
    linha = f"Error opening input file rtsp://Admin:{SENHA}@192.168.35.18:554/cam/realmonitor?channel=1"
    out = redact_url_credentials(linha)
    assert SENHA not in out
    assert "***" in out


def test_username_is_preserved():
    """Usuário ajuda a diagnosticar login errado e não é o segredo."""
    out = redact_url_credentials(f"rtsp://Admin:{SENHA}@10.0.0.1:554/x")
    assert "Admin" in out
    assert SENHA not in out


def test_host_and_path_are_preserved():
    out = redact_url_credentials(f"rtsp://u:{SENHA}@192.168.35.18:554/cam/realmonitor?channel=2&subtype=0")
    assert "192.168.35.18:554" in out
    assert "channel=2" in out
    assert SENHA not in out


def test_other_schemes_also_redacted():
    """O mesmo par usuário:senha aparece em URL de ONVIF/CGI, não só RTSP."""
    for scheme in ("http", "https", "rtsps"):
        out = redact_url_credentials(f"{scheme}://admin:{SENHA}@host/cgi-bin/x.cgi")
        assert SENHA not in out


def test_multiple_urls_in_one_line():
    out = redact_url_credentials(f"tentou rtsp://a:{SENHA}@h1/x e depois rtsp://b:{SENHA}@h2/y")
    assert SENHA not in out
    assert out.count("***") == 2


def test_text_without_url_passes_through():
    assert redact_url_credentials("Connection timed out") == "Connection timed out"


def test_empty_and_none_safe():
    assert redact_url_credentials("") == ""


def test_url_without_credentials_unchanged():
    url = "rtsp://192.168.35.18:554/cam/realmonitor?channel=1"
    assert redact_url_credentials(url) == url


def test_redact_bytes_decodes_and_redacts():
    raw = f"rtsp://admin:{SENHA}@h/x".encode()
    out = redact_bytes(raw)
    assert SENHA not in out and "***" in out


def test_redact_bytes_empty():
    assert redact_bytes(b"") == ""
