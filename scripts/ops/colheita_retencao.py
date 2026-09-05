"""Mede a borda da retenção do DVR pelo MESMO caminho que a mineração usa.

Pede um clipe de 6s de N dias atrás, num canal só, e vê se volta byte. Onde
para de voltar é a borda. Leitura pura, um playback de cada vez, com pausa —
nunca rodar junto com uma colheita (o anti-lockout do gravador é real).
"""
import os
import sys
import time
from datetime import datetime, timedelta

BASE = os.path.expanduser("~/colheita-full-0902")
os.chdir(BASE)
sys.path.insert(0, BASE)
os.environ["XDG_STATE_HOME"] = os.path.join(BASE, "state")
for linha in open(os.path.expanduser("~/.config/recognition/edge-sync-agent.env")):
    linha = linha.strip()
    if linha and not linha.startswith("#") and "=" in linha:
        k, _, v = linha.partition("=")
        os.environ.setdefault(k, v)

from app.logging_setup import install_redacted_logging  # noqa: E402

install_redacted_logging()
import logging  # noqa: E402

logging.disable(logging.WARNING)

from app.collector.replay_miner import _pull_clip_bytes  # noqa: E402
from app.recorder_factory import build_recorder_client_from_env  # noqa: E402

CANAL_CAM = sys.argv[1]
rec = build_recorder_client_from_env()
# 10:00 é horário de operação garantido: se voltar vazio ali, é retenção, não
# "a fábrica estava parada".
for dias in range(1, 9):
    alvo = (datetime.now() - timedelta(days=dias)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    try:
        b = _pull_clip_bytes(rec, CANAL_CAM, alvo, alvo + timedelta(seconds=6))
        print(f"D-{dias} {alvo:%Y-%m-%d %H:%M} -> {len(b)} bytes  GRAVACAO EXISTE")
    except Exception as exc:  # noqa: BLE001 — é isso que estamos medindo
        print(f"D-{dias} {alvo:%Y-%m-%d %H:%M} -> VAZIO ({type(exc).__name__})")
    time.sleep(5)
