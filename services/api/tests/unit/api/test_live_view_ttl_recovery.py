"""Regressão TEMPORAL do live view — player parado por mais tempo que o TTL
do sinal de espectador, com a TELA ABERTA (mesma família do commit 2caeace,
"live view parava sozinho a cada ~90s").

`test_live_view_stability.py` trava FATOS estáticos sobre a constante
`_HLS_INACTIVITY_TTL` (é maior que o pior ciclo do player; é diferente do
ócio do FFmpeg local). Este arquivo trava o COMPORTAMENTO ao longo do
tempo: chama `serve_hls` de verdade via o client Flask, com um Redis fake
cujo relógio é avançado à mão pelo teste (nunca dorme de verdade), e reproduz
a sequência descrita no commit:

    1. manifesto pedido            -> epi:stream:{id}:active nasce/renova
    2. requisições PARAM            -> player em stall/backoff, tela aberta
    3. GET /edge/live-view/wanted   -> ainda vê a câmera como "wanted"?
    4. player retoma                -> o que acontece na PRÓXIMA requisição?

`GET /edge/live-view/wanted` (app/api/v1/edge/routes.py::list_live_view_wanted)
lê exatamente `r.exists(f"epi:stream:{camera_id}:active")` na MESMA chave —
replicado aqui direto no fake (sem montar autenticação de device) porque é
essa leitura, e não o endpoint em si, que é o observador do bug.

Contrato travado (estabelecido por 2caeace, stream_handlers.py:402):
  A. a chave sobrevive ao pior ciclo REAL de reconexão do player (stall 14s +
     backoff 1/2/5s, inclusive quando o primeiro reconnect esbarra num 425 e
     o watchdog rearma — o próprio commit cita "retentativas de 425" como o
     motivo de a janela ter passado de 30s) — o edge NUNCA é avisado a parar
     enquanto a tela segue aberta;
  B. MESMO que o hiato ultrapasse o TTL de verdade (sinal chega a expirar), a
     renovação em serve_hls é INCONDICIONAL: a PRÓXIMA requisição do player
     revive o sinal do zero — não existe beco sem saída que só o reload da
     tela resolveria.
"""
from unittest.mock import patch

from app.api.v1.cameras import stream_handlers as sh
from app.core.playback_token import mint_playback_token

CAM = "eb1501db-82ad-485a-a441-5c665b4e5a28"
_ACTIVE_KEY = f"epi:stream:{CAM}:active"

# CameraPlayer.tsx (apps/frontend/src/components/monitoring/CameraPlayer.tsx):
#   STALL_TIMEOUT_MS = 14000            (linha 7)
#   BACKOFF_DELAYS_MS = [1000, 2000, 5000]   (linha 12)
_STALL_TIMEOUT_S = 14
_BACKOFF_DELAYS_S = (1, 2, 5)

# Pior caso realista com DOIS ciclos de watchdog em cascata: o primeiro
# reconnect (backoff[0]=1s) ainda esbarra num 425 do edge não pronto -> o
# watchdog de stall (14s) rearma e dispara de novo, desta vez com
# backoff[1]=2s. É exatamente o cenário que a mensagem do commit 2caeace cita
# ("Somado às retentativas de 425, a janela sem request passava de 30s") —
# 14+1+14+2 = 31s: maior que o HLS_INACTIVITY_TIMEOUT antigo (30s), menor que
# o HLS_VIEWER_TTL atual (90s).
_TWO_STALL_CYCLES_GAP_S = (
    _STALL_TIMEOUT_S + _BACKOFF_DELAYS_S[0] + _STALL_TIMEOUT_S + _BACKOFF_DELAYS_S[1]
)


def _tokenized_url(filename: str = "stream.m3u8") -> str:
    return f"/api/cameras/{CAM}/stream/s/{mint_playback_token(CAM)}/{filename}"


class _Clock:
    """Relógio falso avançado manualmente pelo teste — sem sleep real."""

    def __init__(self, t0: float = 1_700_000_000.0):
        self.now = t0

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _FakeTTLRedis:
    """Subconjunto de redis-py usado pelo mecanismo (setex/exists/get/ttl),
    com expiração calculada pelo `_Clock` injetado — não pelo relógio real do
    processo. É isso que permite simular minutos de hiato sem dormir.
    """

    def __init__(self, clock: _Clock):
        self._clock = clock
        self._store: dict[str, tuple[object, float]] = {}

    def setex(self, key: str, ttl: int, value):  # noqa: ANN001
        self._store[key] = (value, self._clock.now + ttl)
        return True

    def _live_value(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if self._clock.now >= expire_at:
            del self._store[key]
            return None
        return value

    def exists(self, key: str) -> int:
        return 1 if self._live_value(key) is not None else 0

    def get(self, key: str):
        return self._live_value(key)

    def ttl(self, key: str) -> int:
        entry = self._store.get(key)
        if entry is None:
            return -2
        _, expire_at = entry
        remaining = expire_at - self._clock.now
        return int(remaining) if remaining > 0 else -2

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _EdgeContentRedis:
    """Só o suficiente pro bloco LV-1 do serve_hls: playlist do edge sempre
    presente -> 200 rápido, sem tocar LocalStreamManager/DB. O que importa
    pra este arquivo é exclusivamente a renovação de epi:stream:{id}:active,
    que acontece ANTES dessa decisão (linha ~402)."""

    def get(self, key: str):
        return b"#EXTM3U\n#EXT-X-VERSION:3\n"

    def exists(self, key: str) -> int:
        return 1


_PATCH_BINARY_REDIS = "app.api.v1.cameras.stream_handlers._get_binary_redis"
_PATCH_SEGMENTS_REDIS = "app.api.v1.cameras.stream_handlers.get_segments_redis"


def _request_manifest(client, redis_fake: _FakeTTLRedis):
    with (
        patch(_PATCH_BINARY_REDIS, return_value=_EdgeContentRedis()),
        patch(_PATCH_SEGMENTS_REDIS, return_value=redis_fake),
    ):
        return client.get(_tokenized_url())


class TestSinalDeEspectadorSobreviveAoHiatoDoPlayer:
    """Contrato A — o pior ciclo real de reconexão não pode derrubar o sinal."""

    def test_dois_ciclos_de_stall_em_cascata_nao_derrubam_o_sinal(self, client):
        clock = _Clock()
        redis_fake = _FakeTTLRedis(clock)

        resp = _request_manifest(client, redis_fake)
        assert resp.status_code == 200
        assert redis_fake.exists(_ACTIVE_KEY) == 1

        # Player em stall/backoff: nenhuma requisição chega nesse intervalo,
        # mas a TELA continua aberta.
        clock.advance(_TWO_STALL_CYCLES_GAP_S)

        # Isto é EXATAMENTE o que GET /edge/live-view/wanted enxergaria nesse
        # instante (list_live_view_wanted faz r.exists(f"epi:stream:{id}:active")
        # sobre a mesma chave) — se cair aqui, o edge é mandado parar com a
        # tela aberta, que é o sintoma do bug original.
        assert redis_fake.exists(_ACTIVE_KEY) == 1, (
            "sinal de espectador caiu ANTES do player conseguir se reconectar "
            "— /wanted pararia de incluir a câmera com a tela ainda aberta "
            "(o bug que o commit 2caeace corrigiu)"
        )

        # Player retoma.
        resp2 = _request_manifest(client, redis_fake)
        assert resp2.status_code == 200
        assert redis_fake.exists(_ACTIVE_KEY) == 1
        assert redis_fake.ttl(_ACTIVE_KEY) == sh._HLS_INACTIVITY_TTL


class TestAutoCuraAposHiatoMaiorQueOTtl:
    """Contrato B — mesmo se o hiato passar do TTL de verdade, a PRÓXIMA
    requisição do player tem que reviver o sinal sozinha (sem exigir reload
    da tela)."""

    def test_sinal_expira_de_verdade_mas_proximo_pedido_reativa(self, client):
        clock = _Clock()
        redis_fake = _FakeTTLRedis(clock)

        _request_manifest(client, redis_fake)
        assert redis_fake.exists(_ACTIVE_KEY) == 1

        # Hiato REAL, maior que o próprio TTL configurado — cenário explícito
        # da missão: "player parado por mais tempo que o TTL... com a tela
        # aberta". Aqui o sinal DEVE cair (correto — é o que sinaliza pro
        # /wanted que ninguém está olhando de verdade); o que não pode
        # acontecer é ele não voltar depois.
        clock.advance(sh._HLS_INACTIVITY_TTL + 5)
        assert redis_fake.exists(_ACTIVE_KEY) == 0, (
            "sanity check: neste ponto o sinal realmente deveria ter expirado"
        )

        # Tela continua aberta, player finalmente consegue pedir de novo.
        resp2 = _request_manifest(client, redis_fake)
        assert resp2.status_code == 200
        assert redis_fake.exists(_ACTIVE_KEY) == 1, (
            "player retomou e o sinal NÃO reviveu — beco sem saída que só um "
            "reload manual da tela resolveria"
        )
        assert redis_fake.ttl(_ACTIVE_KEY) == sh._HLS_INACTIVITY_TTL
