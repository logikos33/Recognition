"""
Testa o desenho de buckets do rate limit do live view (mutirão 04/08).

Contexto: log de produção (04/08 15:06-15:08) mostrou o bucket global
"tenant-api-global" (300/min POR IP) derrubando .m3u8/.ts E o preflight OPTIONS de
/stream/start — um video wall de N câmeras atrás do mesmo IP de fábrica derruba os
outros usuários daquele IP. Ver app/core/rate_limiting.py e
app/api/v1/cameras/stream_handlers.py para o desenho completo.

RATELIMIT_ENABLED é False por padrão em TESTING (app/__init__.py) — os testes abaixo
religam o limiter explicitamente (limiter.init_app com RATELIMIT_ENABLED=True) num app
próprio por teste, e injetam limites BAIXOS via monkeypatch dos módulos de constantes
para não depender de dezenas/centenas de requests reais.

Por que monkeypatch funciona aqui: os limites "estáticos" (piso IP, preflight, buckets
de vídeo) são registrados como CALLABLES (`_ip_floor_limit`, `_options_limit`,
`_hls_token_limit`, `_hls_ip_floor_limit`), não strings literais — o flask-limiter
avalia o callable A CADA REQUEST, então o valor lido é sempre o do módulo NO MOMENTO
da request, não o do momento em que o decorator rodou. login/register/progress-callback
usam string literal (`@limiter.limit("10 per minute")`) — decisão de design de quem
escreveu essas rotas, não algo que esta task mudou — então os testes desses três usam
o valor real em vez de injetar um baixo.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from flask import Response
from flask_jwt_extended import create_access_token

from app import create_app
from app.api.v1.cameras import stream_handlers as sh
from app.core import rate_limiting
from app.core.playback_token import mint_playback_token
from app.extensions import limiter

VALID_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

_PATCH_BINARY_REDIS = "app.api.v1.cameras.stream_handlers._get_binary_redis"
_PATCH_TEXT_REDIS = "app.api.v1.cameras.stream_handlers._get_redis"
_PATCH_SEGMENTS_REDIS = "app.api.v1.cameras.stream_handlers.get_segments_redis"


@pytest.fixture
def limited_app():
    """App de teste com o limiter LIGADO, storage isolado por teste.

    create_app() já chama limiter.init_app(application) internamente com
    RATELIMIT_ENABLED=False (TESTING) — essa primeira chamada retorna cedo,
    sem registrar o before_request hook nem trocar o storage (ver
    Limiter.init_app: "if not self.enabled: return" é a segunda linha).
    A chamada AQUI, com RATELIMIT_ENABLED=True, é a primeira que de fato
    inicializa esta app: troca self._storage por uma instância memory://
    nova (isolando os contadores deste teste dos demais) e registra os hooks
    nesta app pela primeira vez.
    """
    application = create_app("testing")
    application.config["RATELIMIT_ENABLED"] = True
    application.config["RATELIMIT_STORAGE_URI"] = "memory://"
    limiter.init_app(application)
    yield application
    limiter.enabled = False


@pytest.fixture
def limited_client(limited_app):
    return limited_app.test_client()


def _auth_header(app, tenant_id: str = "tenant-A", user_id: str = "user-1") -> dict:
    with app.app_context():
        token = create_access_token(
            identity=user_id,
            additional_claims={"tenant_id": tenant_id, "sub": user_id},
        )
    return {"Authorization": f"Bearer {token}"}


def _hls_url(camera_id: str = VALID_UUID) -> str:
    token = mint_playback_token(camera_id)
    return f"/api/cameras/{camera_id}/stream/s/{token}/stream.m3u8"


def _mock_video_redis():
    """Redis mockado pro caminho serve_hls não achar segmento de edge nem
    stream local — cai no fallback de disco, que o teste também mocka."""
    redis_bin = MagicMock()
    redis_bin.get.return_value = None
    redis_bin.exists.return_value = 0
    return redis_bin


# ── (a) preflight OPTIONS não consome o bucket geral, mas tem teto próprio ──


class TestOptionsBucket:
    def test_options_preflight_does_not_consume_general_bucket(
        self, limited_app, limited_client, monkeypatch
    ):
        """OPTIONS repetido não deve tocar o piso por IP do bucket geral —
        achado de produção: era exatamente isso que derrubava /stream/start."""
        monkeypatch.setattr(rate_limiting, "DEFAULT_IP_LIMIT", "1 per minute")
        monkeypatch.setattr(rate_limiting, "OPTIONS_IP_LIMIT", "20 per minute")
        rate_limiting.clear_limit_cache()

        camera_id = str(uuid.uuid4())
        for _ in range(5):
            resp = limited_client.options(f"/api/cameras/{camera_id}/stream/start")
            assert resp.status_code == 200

        # o piso do bucket geral (1/min) segue de pé pra uma request de verdade
        resp = limited_client.get("/api/cameras")
        assert resp.status_code != 429

    def test_options_preflight_still_has_its_own_ceiling(
        self, limited_app, limited_client, monkeypatch
    ):
        """Preflight não pode ficar SEM limite nenhum — vetor de DoS."""
        monkeypatch.setattr(rate_limiting, "OPTIONS_IP_LIMIT", "3 per minute")
        rate_limiting.clear_limit_cache()

        camera_id = str(uuid.uuid4())
        codes = [
            limited_client.options(f"/api/cameras/{camera_id}/stream/start").status_code
            for _ in range(6)
        ]
        assert codes.count(429) >= 1


# ── (b) vídeo HLS usa bucket próprio, isolado do bucket geral ───────────────


class TestVideoBucket:
    def test_video_flood_does_not_trip_general_bucket(
        self, limited_app, limited_client, monkeypatch
    ):
        """N requisições de vídeo não podem derrubar uma chamada de API geral
        do mesmo IP — era o video wall de 8 câmeras derrubando o resto."""
        monkeypatch.setattr(sh, "HLS_TOKEN_LIMIT", "50 per minute")
        monkeypatch.setattr(sh, "HLS_IP_FLOOR_LIMIT", "50 per minute")
        monkeypatch.setattr(rate_limiting, "DEFAULT_IP_LIMIT", "2 per minute")
        rate_limiting.clear_limit_cache()

        redis_bin = _mock_video_redis()
        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_TEXT_REDIS, return_value=MagicMock()),
            patch(_PATCH_SEGMENTS_REDIS, return_value=MagicMock()),
            patch("os.path.isfile", return_value=True),
            patch("flask.send_from_directory", return_value=Response("ok", 200)),
        ):
            for _ in range(6):  # > piso do bucket geral (2/min) injetado acima
                resp = limited_client.get(_hls_url())
                assert resp.status_code == 200

        # bucket geral segue intacto — a inundação de vídeo não o tocou
        resp = limited_client.get("/api/cameras")
        assert resp.status_code != 429

    def test_video_session_bucket_has_its_own_ceiling(
        self, limited_app, limited_client, monkeypatch
    ):
        """O bucket de vídeo não é ilimitado — token de sessão tem teto."""
        monkeypatch.setattr(sh, "HLS_TOKEN_LIMIT", "3 per minute")
        monkeypatch.setattr(sh, "HLS_IP_FLOOR_LIMIT", "1000 per minute")

        redis_bin = _mock_video_redis()
        url = _hls_url()  # mesmo token em todas as chamadas — mesma "sessão"
        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_TEXT_REDIS, return_value=MagicMock()),
            patch(_PATCH_SEGMENTS_REDIS, return_value=MagicMock()),
            patch("os.path.isfile", return_value=True),
            patch("flask.send_from_directory", return_value=Response("ok", 200)),
        ):
            codes = [limited_client.get(url).status_code for _ in range(5)]
        assert codes.count(429) >= 1

    def test_video_ip_floor_covers_requests_without_token(
        self, limited_app, limited_client, monkeypatch
    ):
        """Rota legada sem token (compat) também fica sob o piso por IP do
        bucket de vídeo — não fica de fora por acidente."""
        monkeypatch.setenv("HLS_REQUIRE_PLAYBACK_TOKEN", "0")
        monkeypatch.setattr(sh, "HLS_TOKEN_LIMIT", "1000 per minute")
        monkeypatch.setattr(sh, "HLS_IP_FLOOR_LIMIT", "3 per minute")

        redis_bin = _mock_video_redis()
        legacy_url = f"/api/cameras/{VALID_UUID}/stream/stream.m3u8"
        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_TEXT_REDIS, return_value=MagicMock()),
            patch(_PATCH_SEGMENTS_REDIS, return_value=MagicMock()),
            patch("os.path.isfile", return_value=True),
            patch("flask.send_from_directory", return_value=Response("ok", 200)),
        ):
            codes = [limited_client.get(legacy_url).status_code for _ in range(5)]
        assert codes.count(429) >= 1


# ── (c) login segue barrado no limite dedicado (não afrouxou) ───────────────


class TestAuthDedicatedLimitsUnchanged:
    def test_login_repeated_attempts_hit_dedicated_limit(self, limited_app, limited_client):
        """/api/auth/login usa @limiter.limit("10 per minute") por IP — string
        literal, não injetável por monkeypatch (decisão pré-existente, fora
        do escopo desta task). As 10 primeiras não podem ser barradas; a
        partir da 11ª, sim."""
        payload = {"email": "nope@example.com", "password": "wrong"}
        codes = [
            limited_client.post("/api/auth/login", json=payload).status_code
            for _ in range(12)
        ]
        assert codes[:10].count(429) == 0
        assert codes.count(429) >= 1

    # ── (d) progress-callback mantém 60/min (não afrouxou) ──────────────────

    def test_progress_callback_keeps_60_per_minute(self, limited_app, limited_client):
        """POST .../progress-callback usa @limiter.limit("60 per minute") por
        IP — sem X-Callback-Token retorna 401 rápido (sem tocar DB), então dá
        pra bater as 60 sem mockar nada. As 60 primeiras não podem ser
        barradas; a 61ª sim."""
        job_id = str(uuid.uuid4())
        url = f"/api/v1/training/jobs/{job_id}/progress-callback"
        codes = [limited_client.post(url, json={}).status_code for _ in range(61)]
        assert codes[:60].count(429) == 0
        assert codes[60] == 429


# ── (e) bucket geral: autenticado por usuário, anônimo por IP ───────────────


class TestGeneralBucketKeying:
    def test_authenticated_request_is_limited_by_user(
        self, limited_app, limited_client, monkeypatch
    ):
        monkeypatch.setattr(rate_limiting, "DEFAULT_API_LIMIT", "2 per minute")
        monkeypatch.setattr(rate_limiting, "DEFAULT_IP_LIMIT", "1000 per minute")
        rate_limiting.clear_limit_cache()

        headers = _auth_header(limited_app)
        codes = [
            limited_client.get("/api/cameras", headers=headers).status_code
            for _ in range(4)
        ]
        assert codes.count(429) >= 1

    def test_anonymous_request_is_limited_by_ip_not_by_user_bucket(
        self, limited_app, limited_client, monkeypatch
    ):
        """Sem JWT, a request não pode herdar o teto (mais apertado) do
        bucket por usuário — exempt_when=is_anonymous_request cuida disso.
        O piso por IP segue sendo a única defesa."""
        monkeypatch.setattr(rate_limiting, "DEFAULT_API_LIMIT", "1 per minute")
        monkeypatch.setattr(rate_limiting, "DEFAULT_IP_LIMIT", "3 per minute")
        rate_limiting.clear_limit_cache()

        codes = [limited_client.get("/api/cameras").status_code for _ in range(5)]
        # se caísse no bucket de usuário (1/min), já teria tomado 429 na 2ª
        assert codes[:3].count(429) == 0
        assert codes.count(429) >= 1

    def test_authenticated_request_also_bound_by_ip_floor(
        self, limited_app, limited_client, monkeypatch
    ):
        """Defesa em profundidade: mesmo autenticado, o piso por IP também se
        aplica — várias contas atrás do mesmo IP não somam mais que o piso."""
        monkeypatch.setattr(rate_limiting, "DEFAULT_API_LIMIT", "1000 per minute")
        monkeypatch.setattr(rate_limiting, "DEFAULT_IP_LIMIT", "2 per minute")
        rate_limiting.clear_limit_cache()

        headers = _auth_header(limited_app, tenant_id="tenant-B", user_id="user-2")
        codes = [
            limited_client.get("/api/cameras", headers=headers).status_code
            for _ in range(4)
        ]
        assert codes.count(429) >= 1
