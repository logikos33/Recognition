"""
Recognition — fonte de frame a partir do HLS que o EDGE já empurra.

Por que isto existe: `inference_loop` nasceu abrindo RTSP direto da câmera
(`cv2.VideoCapture(rtsp_url)`), e a nuvem **não alcança** a câmera — ela vive
atrás de MikroTik/WireGuard com discagem outbound (ADR-0020), e o gravador
Intelbras/Hikvision trava por lockout se exposto. Esse era o elo real do #519.

O caminho que JÁ funciona é o inverso e já está de pé: o box roda
`edge-live-view.service` (RTSP → HLS → push), e a nuvem guarda cada segmento
em `epi:edge_hls:{camera_id}:{filename}` com TTL de 30s
(`api/v1/edge/routes.py::upload_live_view_segment`). O gatilho é a chave
`epi:stream:{camera_id}:active`: existindo, o box transmite; sumindo, ele para
— e é a MESMA chave que `inference_loop` já usa para saber se continua vivo.

Então "ver ao vivo pela nuvem" não pede pipeline novo nem OTA no box: pede
trocar a fonte de frame por este módulo.

⚠️ Precisão da latência: derivada do TTL restante da chave
(`idade = TTL_total - ttl_restante`), que o Redis reporta em SEGUNDOS
INTEIROS. Logo a medida tem resolução de ~1s e é um PISO — não inclui o tempo
que o frame passou dentro do segmento antes do corte. Some-se `hls_time` (2s
hoje) para o pior caso. Isto é medição honesta e barata; se algum dia
precisarmos de milissegundos, o caminho é a rota de upload carimbar o instante
de chegada, não refinar esta conta.
"""
from __future__ import annotations

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

#: Espelha `_HLS_SEGMENT_TTL` de api/v1/edge/routes.py. Duplicado de propósito:
#: aquele módulo é da camada de rota e importá-lo aqui puxaria Flask para
#: dentro do worker. Se lá mudar, muda aqui — há teste que trava os dois juntos.
TTL_SEGMENTO_S = 30

_PREFIXO = "epi:edge_hls"


def chave_playlist(camera_id: str) -> str:
    return f"{_PREFIXO}:{camera_id}:stream.m3u8"


def chave_segmento(camera_id: str, filename: str) -> str:
    return f"{_PREFIXO}:{camera_id}:{filename}"


def segmentos_da_playlist(playlist: bytes) -> list[str]:
    """Nomes dos `.ts` anunciados, na ordem em que o ffmpeg os escreveu.

    ⛔ Não ordenar por nome: o ffmpeg escreve `stream9.ts` e `stream10.ts`, e
    ordem lexicográfica coloca o 10 ANTES do 9 — o consumidor andaria para trás
    sem erro nenhum. A playlist já vem na ordem certa; ela é a fonte.
    """
    nomes: list[str] = []
    for linha in playlist.decode("utf-8", errors="ignore").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and linha.endswith(".ts"):
            nomes.append(linha)
    return nomes


class FonteHlsDoEdge:
    """Entrega o frame mais recente que o edge empurrou para uma câmera.

    Mantém a marca do último segmento consumido para (a) não reprocessar o
    mesmo frame e (b) CONTAR o que expirou sem ser visto — a perda por TTL é
    medida, não suposta.
    """

    def __init__(self, camera_id: str, redis_binario, ttl_total_s: int = TTL_SEGMENTO_S) -> None:
        self._camera_id = camera_id
        self._redis = redis_binario
        self._ttl_total = ttl_total_s
        self._ultimo_consumido: str | None = None
        #: segmentos que a playlist anunciou e que nunca chegamos a consumir
        self.perdidos_por_ttl = 0
        self.consumidos = 0

    def _idade_do_segmento_s(self, chave: str) -> float | None:
        """Idade pelo TTL restante. None quando o Redis não sabe (-1/-2)."""
        try:
            ttl = self._redis.ttl(chave)
        except Exception as exc:
            logger.debug("hls_ttl_falhou camera=%s err=%s", self._camera_id, exc)
            return None
        if ttl is None or ttl < 0:
            return None
        return float(self._ttl_total - int(ttl))

    def proximo_frame(self):
        """`(frame, idade_s)` do segmento mais novo ainda não consumido.

        `(None, None)` quando não há segmento novo — o chamador deve dormir e
        tentar de novo, exatamente como fazia com `cap.read()` devolvendo False.

        ⚠️ O `import cv2` fica lá embaixo, colado no decode, ⛔ não aqui em
        cima. A maioria absoluta das chamadas sai antes de decodificar
        (playlist ausente, nenhum segmento novo, segmento expirado) e não tem
        por que exigir o decodificador. Já nasceu no topo uma vez e a suíte
        inteira reprovou: basta um teste anterior deixar o `cv2` meio
        carregado para este caminho morrer sem nem chegar ao `return`.
        """
        try:
            playlist = self._redis.get(chave_playlist(self._camera_id))
        except Exception as exc:
            logger.warning("hls_playlist_falhou camera=%s err=%s", self._camera_id, exc)
            return None, None
        if not playlist:
            return None, None

        nomes = segmentos_da_playlist(playlist)
        if not nomes:
            return None, None

        # Só o mais novo interessa: queremos AO VIVO, não a fila inteira. O que
        # ficou para trás é perda declarada, não dívida a processar.
        alvo = nomes[-1]
        if alvo == self._ultimo_consumido:
            return None, None

        if self._ultimo_consumido is not None and self._ultimo_consumido in nomes:
            pulados = len(nomes) - 1 - nomes.index(self._ultimo_consumido) - 1
            if pulados > 0:
                self.perdidos_por_ttl += pulados

        chave = chave_segmento(self._camera_id, alvo)
        try:
            dados = self._redis.get(chave)
        except Exception as exc:
            logger.warning("hls_segmento_falhou camera=%s err=%s", self._camera_id, exc)
            return None, None
        if not dados:
            # Anunciado na playlist mas já expirado: é exatamente a perda que
            # este contador existe para tornar visível.
            self.perdidos_por_ttl += 1
            self._ultimo_consumido = alvo
            return None, None

        idade = self._idade_do_segmento_s(chave)

        # cv2 não decodifica de memória para vídeo (só imagem), então o `.ts`
        # passa por arquivo temporário. É o decodificador que o loop já usa —
        # zero dependência nova.
        import cv2  # noqa: PLC0415

        caminho = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as tmp:
                tmp.write(dados)
                caminho = tmp.name
            cap = cv2.VideoCapture(caminho)
            try:
                ok, frame = cap.read()
            finally:
                cap.release()
        except Exception as exc:
            logger.warning("hls_decode_falhou camera=%s err=%s", self._camera_id, exc)
            return None, None
        finally:
            if caminho:
                try:
                    os.unlink(caminho)
                except OSError:
                    pass

        self._ultimo_consumido = alvo
        if not ok or frame is None:
            logger.warning(
                "hls_segmento_sem_frame camera=%s seg=%s bytes=%d — codec do "
                "gravador pode não ser decodificável aqui (HEVC no stream "
                "principal); ver RECORDER_STREAM_SUBTYPE",
                self._camera_id, alvo, len(dados),
            )
            return None, None

        self.consumidos += 1
        return frame, idade
