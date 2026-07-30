"""Roda FFmpeg local transformando o RTSP da câmera em segmentos HLS.

LV-2 (task-060, "o modelo da RVB"): o transcode acontece AQUI, no edge, não
na nuvem — a nuvem nunca alcança a câmera atrás do NVR numa LAN isolada
(ADR-0020), então o LocalStreamManager cloud-side (ADR-0030) não serve pra
esse cenário.

Mesmos flags de baixa latência que o LocalStreamManager já usa (segmento de
1s, playlist de 3, `-c:v copy` por padrão) — reaproveitados de propósito pra
que a experiência de latência seja a mesma que a de uma câmera cloud-direct.

DISCO (ADR-0033/0045 — o 128GB do Orin é SO+app, nunca destino de
armazenamento): `delete_segments` + `hls_list_size=3` mantêm o diretório em
~3-5 segmentos (poucos MB) de forma permanente. É buffer transitório, mesmo
padrão do `/tmp/hls/` do LocalStreamManager — não cresce com o tempo.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..recorder_client import RecorderError
from ..rtsp_validator import RTSPUrlValidator

logger = logging.getLogger(__name__)

_STDERR_TAIL = 500


class HlsTranscoder:
    """Um processo FFmpeg por câmera, escrevendo HLS num diretório local."""

    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        output_dir: str,
        segment_seconds: int = 1,
        list_size: int = 3,
        video_codec: str = "copy",
        popen: Any = subprocess.Popen,
    ) -> None:
        self._camera_id = camera_id
        self._rtsp_url = RTSPUrlValidator.validate(rtsp_url)
        self._output_dir = Path(output_dir)
        self._segment_seconds = segment_seconds
        self._list_size = list_size
        self._video_codec = video_codec
        self._popen = popen
        self._process: Any = None

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @property
    def playlist_path(self) -> Path:
        return self._output_dir / "stream.m3u8"

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        """Sobe o FFmpeg. No-op se já está rodando."""
        if self.is_running():
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-nostdin",
            "-loglevel", "error",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-probesize", "32",
            "-analyzeduration", "0",
            "-rtsp_transport", "tcp",
            "-i", self._rtsp_url,
            "-c:v", self._video_codec,
        ]
        if self._video_codec == "libx264":
            cmd.extend(["-preset", "ultrafast", "-tune", "zerolatency"])
        cmd.append("-an")  # sem áudio — mesma escolha do LocalStreamManager
        cmd.extend([
            "-f", "hls",
            "-hls_time", str(self._segment_seconds),
            "-hls_list_size", str(self._list_size),
            "-hls_flags", "delete_segments+omit_endlist",
            str(self.playlist_path),
        ])

        try:
            self._process = self._popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
        except OSError as exc:
            # Nunca interpolar cmd/rtsp_url — carrega credencial do gravador.
            raise RecorderError(f"ffmpeg indisponível para o live view: {exc}") from exc

        logger.info("live_view_transcoder_started camera=%s", self._camera_id)

    def stop(self) -> None:
        """Encerra o FFmpeg e limpa o diretório de segmentos."""
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

        # Buffer transitório — não deixa segmento órfão ocupando disco.
        try:
            shutil.rmtree(self._output_dir, ignore_errors=True)
        except OSError as exc:
            logger.warning("live_view_cleanup_failed camera=%s err=%s", self._camera_id, exc)

        logger.info("live_view_transcoder_stopped camera=%s", self._camera_id)

    def stderr_tail(self) -> str:
        """Últimos bytes do stderr do FFmpeg — só quando o processo já morreu
        (ler de um processo vivo bloquearia)."""
        if self._process is None or self._process.poll() is None:
            return ""
        if self._process.stderr is None:
            return ""
        try:
            raw = self._process.stderr.read()
        except (OSError, ValueError):
            return ""
        if not raw:
            return ""
        return raw.decode(errors="replace")[:_STDERR_TAIL]

    def list_ready_files(self) -> list[Path]:
        """Playlist + segmentos atualmente no diretório, prontos pra push.

        Um `.ts` sendo escrito NESTE instante pelo FFmpeg apareceria truncado
        — o `.m3u8` só lista um segmento depois que ele foi fechado, então
        filtrar pelos nomes que a playlist referencia evita empurrar um
        segmento pela metade (o navegador rejeitaria).
        """
        playlist = self.playlist_path
        if not playlist.is_file():
            return []
        try:
            listed = {
                line.strip()
                for line in playlist.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip() and not line.startswith("#")
            }
        except OSError:
            return []

        files = [playlist]
        for name in sorted(listed):
            candidate = self._output_dir / name
            if candidate.is_file():
                files.append(candidate)
        return files


def build_output_dir(base_dir: str, camera_id: str) -> str:
    return os.path.join(base_dir, camera_id)
