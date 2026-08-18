"""Truncar URL NÃO é mascarar — e este defeito já voltou três vezes.

Histórico:
  1. `rtsp_url[:40]` em tasks/quality_inference.py — corrigido, com comentário
     explicando que os 40 primeiros caracteres de `rtsp://user:senha@host` são
     exatamente o userinfo.
  2. `rtsp_url[:30]` em tasks/quality_recording.py — ficou.
  3. `redis_url[:30]` em queue/celery_app.py — ficou, e imprimia ~14 caracteres
     da senha do Redis A CADA BOOT, em todo log de worker e de API.

O padrão volta por cópia, então a trava é uma varredura do fonte: qualquer
fatiamento de variável que termina em `_url`/`url` é rejeitado. Quem precisa
encurtar uma URL para log usa `app.core.redact.redact_url_credentials`, que
remove o segredo em vez de escondê-lo atrás de um número de caracteres.
"""
from __future__ import annotations

import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[3] / "app"

# `algo_url[:30]`, `url[: 40]`, `RTSP_URL[:n]` — com ou sem espaço.
_FATIA_DE_URL = re.compile(r"\b\w*(?:url|URL)\s*\[\s*:\s*\w+\s*\]")


def test_nenhum_fonte_corta_url_por_caracteres():
    ofensores: list[str] = []
    for caminho in APP.rglob("*.py"):
        for n, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
            sem_comentario = linha.split("#", 1)[0]
            if _FATIA_DE_URL.search(sem_comentario):
                rel = caminho.relative_to(APP.parent)
                ofensores.append(f"{rel}:{n}: {linha.strip()}")

    assert not ofensores, (
        "URL fatiada por caracteres vaza credencial — o userinfo vem PRIMEIRO.\n"
        "Use app.core.redact.redact_url_credentials.\n  " + "\n  ".join(ofensores)
    )


def test_o_redator_realmente_tira_a_senha():
    """Trava de sanidade: se o redator parar de redigir, o teste acima vira teatro."""
    from app.core.redact import redact_url_credentials

    saida = redact_url_credentials("redis://default:senha-secreta@host:6379/0")
    assert "senha-secreta" not in saida
    assert "host:6379" in saida, "não pode apagar o que é diagnóstico útil"

    rtsp = redact_url_credentials("rtsp://admin:hunter2@192.168.1.10:554/cam")
    assert "hunter2" not in rtsp
    assert "192.168.1.10" in rtsp
