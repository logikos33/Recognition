#!/usr/bin/env python3
"""Runner do LOTE 1 — minera ~50 recortes do canal 10 do DVR RVB (iNVD 3032).

Pronto para o Vitor apertar o botão. Espelha a fiação do edge-frame-collector
(`app/collector/__main__.py`): mesma identidade, mesmo upload, mesmo client.

Regras (não negociáveis):
- ⛔ Roda SÓ do Orin (VLAN isolada, outbound — ADR-0020), nunca da nuvem.
- ⛔ Exige `CONFIRM_MINE=1` — a porta deliberada. Sem ela, recusa e explica.
- ⛔ Lê `RECORDER_*`/`EDGE_*` do ENV — nunca de argv, nunca hardcoded, e
  NUNCA imprime valor de credencial, host, caminho identificável ou URL.
- 🔴 Valida ANTES de puxar (canal no map? disco? identidade? DVR responde?) e,
  se faltar algo, falha com mensagem legível dizendo O QUE falta — sem traceback.
- 🔴 Anti-lockout: qualquer 401/403 do gravador ENCERRA a run inteira, sem
  retry, sem variante de credencial (herdado de `ReplayMiner.mine`). Canal
  vazio NÃO é falha de auth.
- ⛔ Não escala além do lote 1: 1 canal, 1 dia, 1 turno.

Uso (no pandora, com o env do edge carregado — ver runbook):
    CONFIRM_MINE=1 python -m scripts.ops.mine_lote1   # ou caminho direto
Ajustes por env (opcionais): LOTE1_CHANNEL(=10), LOTE1_DAY_OFFSET(=1 dia atrás),
LOTE1_MIN_FREE_GB(=8), LOTE1_SHIFT(=tarde).
"""
from __future__ import annotations

import logging
import os
import shutil
import socket
import time
from datetime import date, timedelta

# Silencia INFO/DEBUG do app do edge — o client monta uma URL de playback que
# embute credencial; em nível INFO ela poderia vazar no stdout/journal.
logging.basicConfig(level=logging.WARNING)

try:
    from app.auth.token_manager import build_token_manager_from_env
    from app.collector.frame_uploader import upload_frame
    from app.collector.person_detector import build_person_detector_from_env
    from app.collector.replay_miner import (
        DEFAULT_SHIFTS,
        RecorderAuthError,
        RecorderError,
        ReplayMiner,
        has_disk_reserve,
        run_mining,
    )
    from app.recorder_factory import build_recorder_client_from_env, resolve_channel_map
except ModuleNotFoundError as exc:  # pragma: no cover — só falha fora do box
    print(
        "[mine_lote1] RECUSADO: app do edge não está no PYTHONPATH "
        f"({exc.name}). Rode do Orin, a partir do app deployado "
        "(ver runbook: cd ~/recognition/current && .venv/bin/python ...)."
    )
    raise SystemExit(2) from None


LOTE1_CHANNEL = int(os.environ.get("LOTE1_CHANNEL", "10"))
LOTE1_DAY_OFFSET = int(os.environ.get("LOTE1_DAY_OFFSET", "1"))  # dias atrás (1 = ontem)
MIN_FREE_GB = float(os.environ.get("LOTE1_MIN_FREE_GB", "8"))
MODULE_CODE = os.environ.get("COLLECTOR_MODULE_CODE", "epi")
_SHIFT_BY_LABEL = {s.label: s for s in DEFAULT_SHIFTS}
LOTE1_SHIFT = os.environ.get("LOTE1_SHIFT", "tarde")


def _fail(msg: str, code: int = 2) -> None:
    print(f"[mine_lote1] RECUSADO: {msg}")
    raise SystemExit(code)


def _free_gb() -> float:
    return shutil.disk_usage("/").free / 1024**3


def _dvr_tcp_responds() -> bool:
    """TCP connect sem autenticação — não dispara lockout. Não imprime host."""
    host = os.environ.get("RECORDER_HOST")
    if not host:
        return False
    port = int(os.environ.get("RECORDER_PORT", "554"))
    sock = socket.socket()
    sock.settimeout(5)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def main() -> int:
    # 1) Porta deliberada — antes de qualquer coisa.
    if os.environ.get("CONFIRM_MINE") != "1":
        _fail(
            "CONFIRM_MINE=1 não está setado. É a porta deliberada da mineração "
            "real — exporte-a conscientemente para puxar imagem de "
            "trabalhadores reais em operação (D-106). Sem ela, nada é puxado."
        )

    # 2) Validação ANTES de puxar — cada falha diz O QUE falta, sem traceback.
    channel_map, source_label, _ver = resolve_channel_map(dict(os.environ))
    by_channel = {ch: cam for cam, ch in channel_map.items()}
    if LOTE1_CHANNEL not in by_channel:
        _fail(
            f"canal {LOTE1_CHANNEL} não está registrado no gravador "
            f"(fonte={source_label}; canais mapeados={sorted(by_channel) or 'nenhum'}). "
            f"Registrar a câmera-canal {LOTE1_CHANNEL} no DEV é ato do Vitor "
            "(scripts/ops/import_nvr_channels_rvb.py + RECORDER_CHANNEL_MAP / config da nuvem)."
        )
    if LOTE1_SHIFT not in _SHIFT_BY_LABEL:
        _fail(f"turno '{LOTE1_SHIFT}' inválido; use um de {sorted(_SHIFT_BY_LABEL)}.")
    if shutil.which("ffmpeg") is None:
        _fail(
            "ffmpeg não está no PATH — o pull de playback do DVR depende dele. "
            "Rode com o PATH dos serviços do edge: export PATH=$HOME/.local/bin:$PATH"
        )
    if not has_disk_reserve(min_free_gb=MIN_FREE_GB):
        _fail(
            f"disco abaixo da reserva de {MIN_FREE_GB:.0f} GB — minerar travaria "
            "o device. Libere espaço antes (reserva é intocável)."
        )
    token_source = build_token_manager_from_env()
    if not token_source.has_valid_identity():
        _fail("device sem identidade enrolada (EDGE_DEVICE_KEY_PATH ausente/inválido).")
    api_base = os.environ.get("EDGE_API_URL", "").strip()
    recorder_id = os.environ.get("RECORDER_CLOUD_ID", "").strip()
    if not api_base or not recorder_id:
        _fail("EDGE_API_URL e RECORDER_CLOUD_ID são obrigatórios para subir os recortes.")
    if not _dvr_tcp_responds():
        _fail("DVR não respondeu (TCP) no host/porta do env — verifique a rede/VLAN do Orin.")
    detector = build_person_detector_from_env()
    if detector is None:
        _fail("person_detector desligado (COLLECTOR_PERSON_TRIGGER) — necessário para recortar pessoas.")

    recorder = build_recorder_client_from_env()

    # Metering do upload (contagem + bytes) — envolve o upload real, não o altera.
    # Modo inspeção: LOTE1_SAVE_DIR salva o recorte em disco (para avaliar
    # qualidade antes de subir) em vez de mandar pra nuvem — reversível, ⛔ não
    # sobe imagem de trabalhador real enquanto se valida a corrente.
    save_dir = os.environ.get("LOTE1_SAVE_DIR", "").strip()
    metered = {"count": 0, "bytes": 0}

    def _metered_upload(http, api_base_url, bearer, camera_id, rec_id, frame_bytes, module_code, captured_at):
        metered["count"] += 1
        metered["bytes"] += len(frame_bytes)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            with open(os.path.join(save_dir, f"crop_{metered['count']:04d}.jpg"), "wb") as fh:
                fh.write(frame_bytes)
            return f"local-{metered['count']}"
        return upload_frame(
            http, api_base_url, bearer, camera_id, rec_id, frame_bytes, module_code, captured_at
        )

    miner = ReplayMiner(
        recorder=recorder,
        api_base_url=api_base,
        recorder_id=recorder_id,
        token_source=token_source,
        person_detector=detector,
        module_code=MODULE_CODE,
        min_free_gb=MIN_FREE_GB,
        # ⚠️ O default (3000) foi calibrado só contra fixtures sintéticos e, medido
        # em campo (D-112), REJEITA ~100% dos recortes reais (variância ~150).
        # LOTE1_BLUR_MIN permite baixar para experimentar — mas o problema real é
        # falso-positivo do detector (poste virou "pessoa"), não só o limiar.
        blur_min_variance=float(os.environ.get("LOTE1_BLUR_MIN", "3000")),
        upload_fn=_metered_upload,
        state_path=None,  # lote 1 é one-off — sem persistir estado de campanha
    )

    # 3) Plano mínimo: 1 canal, 1 dia, 1 turno (~40-50 recortes).
    target_day = date.today() - timedelta(days=LOTE1_DAY_OFFSET)
    shift = _SHIFT_BY_LABEL[LOTE1_SHIFT]
    camera_by_channel = {LOTE1_CHANNEL: by_channel[LOTE1_CHANNEL]}

    print(
        f"[mine_lote1] LOTE 1 — canal {LOTE1_CHANNEL} · dia {target_day.isoformat()} · "
        f"turno {shift.label}. CONFIRM_MINE ok, disco ok, identidade ok, DVR responde. "
        "Puxando playback… (anti-lockout: 401/403 encerra tudo, sem retry)"
    )
    free_before = _free_gb()
    t0 = time.monotonic()
    try:
        stats = run_mining(miner, camera_by_channel, days=[target_day], shifts=(shift,))
    except RecorderAuthError:
        _fail(
            "gravador respondeu 401/403 — run ENCERRADA (anti-lockout, sem retry). "
            "⛔ Não reexecute com variante de credencial; a credencial provisionada "
            "precisa ser revista.",
            code=3,
        )
    except RecorderError as exc:
        _fail(f"erro do gravador (não-auth): {type(exc).__name__}. Run encerrada.", code=4)
    elapsed = time.monotonic() - t0
    disk_delta_mb = max(0.0, (free_before - _free_gb()) * 1024)

    # 4) Relatório final — número e tabela, ZERO credencial/host/caminho/URL.
    print("\n=== LOTE 1 — resultado ===")
    print(f"modo                          : {'inspeção local (NÃO subiu)' if save_dir else 'upload p/ nuvem DEV'}")
    print(f"recortes gerados (mantidos)   : {stats.crops_kept}")
    print(f"  descartados: sem pessoa     : {stats.crops_dropped_no_person}")
    print(f"  descartados: borrado        : {stats.crops_dropped_blurry}")
    print(f"  descartados: quase-duplicata: {stats.crops_dropped_duplicate}")
    print(f"janelas puxadas / vazias      : {stats.windows_pulled} / {stats.windows_empty}")
    print(f"frames escaneados             : {stats.frames_scanned}")
    print(f"uploads confirmados           : {metered['count']}")
    print(f"bytes enviados (aprox.)       : {metered['bytes'] / 1024:.0f} KB")
    print(f"delta de disco no Orin        : {disk_delta_mb:.1f} MB (pipeline em memória, ADR-0033/0045)")
    print(f"tempo total                   : {elapsed:.1f} s")
    print(f"uploads falhos                : {stats.uploads_failed}")
    if stats.aborted_reason:
        # Categoria, nunca a mensagem crua (poderia conter detalhe identificável).
        reason = "auth (401/403)" if "auth" in stats.aborted_reason.lower() else "disco/reserva" \
            if "disco" in stats.aborted_reason.lower() or "disk" in stats.aborted_reason.lower() else "outro"
        print(f"🔴 RUN ABORTADA — motivo: {reason}. Nada além do que subiu acima foi puxado.")
        return 3
    print("impacto no gravador           : "
          f"{stats.windows_pulled} pulls de playback; {stats.windows_empty} janelas sem gravação (normal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
