"""download() do runner tem que dizer O QUE veio quando não é zip.

Um 404 do R2 responde XML; sem conferência ele era gravado como dataset e o
erro só aparecia como "Could not find class names" — apontando para o lugar
errado. Quatro pods morreram na época 0 antes de alguém olhar os bytes.
"""
import importlib.util
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

def _achar_remote_train() -> pathlib.Path:
    """Sobe até achar o repo — aritmética de parents[] quebra se a árvore mudar."""
    for base in pathlib.Path(__file__).resolve().parents:
        alvo = base / "training/vast/remote_train.py"
        if alvo.exists():
            return alvo
    raise FileNotFoundError("training/vast/remote_train.py não encontrado")


_SRC = _achar_remote_train()


def _load():
    # O módulo roda no pod (sem as deps da API): carrega isolado.
    spec = importlib.util.spec_from_file_location("_rt", _SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_rt"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rt():
    return _load()


def _resp(body, status=200):
    r = MagicMock()
    r.status = status
    r.read.return_value = body
    r.__enter__ = lambda s: s
    r.__exit__ = lambda *a: False
    return r


def test_xml_de_erro_do_r2_nao_vira_dataset(rt, tmp_path):
    xml = b'<?xml version="1.0"?><Error><Code>NoSuchKey</Code></Error>'
    with patch.object(rt.urllib.request, "urlopen", return_value=_resp(xml)):
        with pytest.raises(RuntimeError) as e:
            rt.download("https://x/y?sig=1", tmp_path / "d.zip", expect_zip=True)
    msg = str(e.value)
    assert "esperava um zip" in msg
    assert "NoSuchKey" in msg, "a mensagem tem que mostrar o que veio"


def test_corpo_vazio_e_recusado(rt, tmp_path):
    with patch.object(rt.urllib.request, "urlopen", return_value=_resp(b"")):
        with pytest.raises(RuntimeError, match="vazio"):
            rt.download("https://x/y", tmp_path / "d.zip", expect_zip=True)


def test_zip_de_verdade_passa(rt, tmp_path):
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("train/_annotations.coco.json", "{}")
    dest = tmp_path / "d.zip"
    with patch.object(rt.urllib.request, "urlopen", return_value=_resp(buf.getvalue())):
        rt.download("https://x/y", dest, expect_zip=True)
    assert dest.read_bytes()[:2] == b"PK"


def test_download_sem_expect_zip_nao_exige_magic(rt, tmp_path):
    dest = tmp_path / "peso.pth"
    with patch.object(rt.urllib.request, "urlopen", return_value=_resp(b"\x80\x02weights")):
        rt.download("https://x/y", dest)
    assert dest.exists()
