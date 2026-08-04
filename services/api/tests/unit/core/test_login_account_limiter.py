"""Tests: app/core/login_account_limiter.py — limite de login por CONTA (D-34).

Contexto (D-32): o rate limit de login existente é por IP (flask-limiter,
`get_remote_address`). Atrás do ProxyFix (`x_for=1`), esse "IP" é o edge da
conexão Railway — varia por conexão TCP. Em produção-DEV, 15 tentativas
falhas de login em conexões distintas para a MESMA conta não dispararam
nenhum 429. Este módulo complementa o limite por IP contando falhas por
CONTA (e-mail) em Redis.

Duas camadas de teste:
  - TestModuleUnit: exercita login_account_limiter.py isoladamente (contador,
    reset, fail-open) com um fake Redis em memória / um fake que sempre falha.
  - TestLoginRouteAccountLimit: reproduz o cenário real via
    POST /api/auth/login, provando que é o limite POR CONTA que dispara —
    inclusive quando cada tentativa vem de um IP diferente (o limite por IP
    dedicado da rota, 10/min/IP, nunca acumula nesse cenário).
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.core import login_account_limiter as lal
from app.core.exceptions import AuthenticationError
from app.extensions import limiter

_GET_REDIS = "app.core.login_account_limiter._get_redis"
AUTH_SVC_PATH = "app.api.v1.auth.routes._get_auth_service"


# ---------------------------------------------------------------------------
# Fakes de Redis — sem fakeredis nas dependências de teste (requirements/api.txt
# não tem); um stub mínimo (INCR/EXPIRE/GET/DELETE) e um "quebrado" (fail-open)
# bastam para o que este módulo faz.
# ---------------------------------------------------------------------------

class _FakeRedis:
    """Redis mínimo o suficiente para exercitar login_account_limiter.

    Sem enforcement real de TTL — a janela é testada via contagem de
    chamadas, não via passagem de tempo (o teto MAX_FAILURES é o que importa
    aqui, não o WINDOW_SECONDS).
    """

    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def get(self, key: str):  # type: ignore[no-untyped-def]
        val = self.store.get(key)
        return str(val) if val is not None else None

    def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, key: str, seconds: int) -> bool:  # noqa: ARG002
        return True

    def delete(self, key: str) -> None:
        self.store.pop(key, None)


class _BrokenRedis:
    """Simula Redis indisponível — todo método levanta."""

    def get(self, *a, **k):  # noqa: ANN002, ANN003, ARG002
        raise ConnectionError("redis down")

    def incr(self, *a, **k):  # noqa: ANN002, ANN003, ARG002
        raise ConnectionError("redis down")

    def expire(self, *a, **k):  # noqa: ANN002, ANN003, ARG002
        raise ConnectionError("redis down")

    def delete(self, *a, **k):  # noqa: ANN002, ANN003, ARG002
        raise ConnectionError("redis down")


# ===========================================================================
# TestModuleUnit — login_account_limiter.py isolado
# ===========================================================================

class TestModuleUnit:
    def test_not_blocked_when_no_failures(self):
        with patch(_GET_REDIS, return_value=_FakeRedis()):
            assert lal.is_blocked("user@test.com") is False

    def test_blocks_after_max_failures(self, monkeypatch):
        monkeypatch.setattr(lal, "MAX_FAILURES", 3)
        fake = _FakeRedis()
        with patch(_GET_REDIS, return_value=fake):
            for _ in range(3):
                lal.register_failure("user@test.com")
            assert lal.is_blocked("user@test.com") is True

    def test_does_not_block_below_threshold(self, monkeypatch):
        monkeypatch.setattr(lal, "MAX_FAILURES", 5)
        fake = _FakeRedis()
        with patch(_GET_REDIS, return_value=fake):
            for _ in range(4):
                lal.register_failure("user@test.com")
            assert lal.is_blocked("user@test.com") is False

    def test_reset_clears_counter(self, monkeypatch):
        monkeypatch.setattr(lal, "MAX_FAILURES", 2)
        fake = _FakeRedis()
        with patch(_GET_REDIS, return_value=fake):
            lal.register_failure("user@test.com")
            lal.register_failure("user@test.com")
            assert lal.is_blocked("user@test.com") is True
            lal.reset("user@test.com")
            assert lal.is_blocked("user@test.com") is False

    def test_counters_are_isolated_per_email(self, monkeypatch):
        monkeypatch.setattr(lal, "MAX_FAILURES", 2)
        fake = _FakeRedis()
        with patch(_GET_REDIS, return_value=fake):
            lal.register_failure("victim@test.com")
            lal.register_failure("victim@test.com")
            assert lal.is_blocked("victim@test.com") is True
            assert lal.is_blocked("other@test.com") is False

    def test_empty_email_never_blocks_or_registers(self):
        fake = _FakeRedis()
        with patch(_GET_REDIS, return_value=fake):
            lal.register_failure("")
            assert lal.is_blocked("") is False
            assert fake.store == {}

    def test_fail_open_is_blocked_never_raises_or_blocks(self):
        with patch(_GET_REDIS, return_value=_BrokenRedis()):
            assert lal.is_blocked("user@test.com") is False

    def test_fail_open_register_failure_never_raises(self):
        with patch(_GET_REDIS, return_value=_BrokenRedis()):
            lal.register_failure("user@test.com")  # não deve levantar

    def test_fail_open_reset_never_raises(self):
        with patch(_GET_REDIS, return_value=_BrokenRedis()):
            lal.reset("user@test.com")  # não deve levantar


# ===========================================================================
# TestLoginRouteAccountLimit — POST /api/auth/login, cenário real (D-32/D-34)
# ===========================================================================

@pytest.fixture
def limited_app():
    """App de teste com o limiter por IP LIGADO — mesmo padrão de
    test_rate_limiting_buckets.py::limited_app. Necessário para provar que o
    429 do cenário abaixo vem do limite por CONTA, não do limite por IP
    (que também está ativo, mas nunca acumula porque cada request usa um IP
    diferente)."""
    application = create_app("testing")
    application.config["RATELIMIT_ENABLED"] = True
    application.config["RATELIMIT_STORAGE_URI"] = "memory://"
    limiter.init_app(application)
    yield application
    limiter.enabled = False


@pytest.fixture
def limited_client(limited_app):
    return limited_app.test_client()


def _failing_auth_service():
    svc = MagicMock()
    svc.login.side_effect = AuthenticationError("Credenciais inválidas")
    return svc


class TestDistinctIpsSameAccount:
    def test_blocks_from_11th_failure_even_with_distinct_ips(
        self, limited_app, limited_client, monkeypatch
    ):
        """Reproduz o log de produção: 15 tentativas falhas para a MESMA
        conta, cada uma "de uma conexão/IP diferente". O limite dedicado por
        IP da rota (10/min/IP) NUNCA acumula aqui — cada IP só aparece uma
        vez. Se ainda assim vier 429 a partir da 11ª tentativa, é o limite
        por CONTA (D-34) que disparou, não o por IP (prova o que D-32
        registrou como falho)."""
        monkeypatch.setattr(lal, "MAX_FAILURES", 10)
        fake = _FakeRedis()
        email = "vitima@rvb.test"

        codes = []
        with patch(AUTH_SVC_PATH, return_value=_failing_auth_service()), \
             patch(_GET_REDIS, return_value=fake):
            for i in range(15):
                resp = limited_client.post(
                    "/api/auth/login",
                    json={"email": email, "password": "wrong"},
                    environ_overrides={"REMOTE_ADDR": f"203.0.113.{i}"},
                )
                codes.append(resp.status_code)

        assert codes[:10].count(429) == 0, codes
        assert all(c == 429 for c in codes[10:]), codes

    def test_429_message_is_generic_no_account_enumeration(
        self, limited_app, limited_client, monkeypatch
    ):
        monkeypatch.setattr(lal, "MAX_FAILURES", 1)
        fake = _FakeRedis()
        email = "vitima2@rvb.test"

        with patch(AUTH_SVC_PATH, return_value=_failing_auth_service()), \
             patch(_GET_REDIS, return_value=fake):
            limited_client.post(
                "/api/auth/login",
                json={"email": email, "password": "wrong"},
                environ_overrides={"REMOTE_ADDR": "198.51.100.1"},
            )
            resp = limited_client.post(
                "/api/auth/login",
                json={"email": email, "password": "wrong"},
                environ_overrides={"REMOTE_ADDR": "198.51.100.2"},
            )

        assert resp.status_code == 429
        body = resp.get_json()
        assert body["success"] is False
        # Mensagem genérica — não menciona "conta", "bloqueada" nem o e-mail.
        assert "conta" not in body["error"].lower()
        assert email not in body["error"]

    def test_other_account_same_ip_not_blocked(
        self, limited_app, limited_client, monkeypatch
    ):
        """Uma conta legítima, a partir do MESMO IP de um atacante que já
        estourou o limite de OUTRA conta, continua processando normalmente —
        o contador é por e-mail, não por IP."""
        monkeypatch.setattr(lal, "MAX_FAILURES", 3)
        fake = _FakeRedis()
        attacker_ip = "203.0.113.99"

        with patch(AUTH_SVC_PATH, return_value=_failing_auth_service()), \
             patch(_GET_REDIS, return_value=fake):
            for _ in range(3):
                limited_client.post(
                    "/api/auth/login",
                    json={"email": "atacado@rvb.test", "password": "wrong"},
                    environ_overrides={"REMOTE_ADDR": attacker_ip},
                )
            # a própria conta atacada já está bloqueada
            blocked_resp = limited_client.post(
                "/api/auth/login",
                json={"email": "atacado@rvb.test", "password": "wrong"},
                environ_overrides={"REMOTE_ADDR": attacker_ip},
            )
            assert blocked_resp.status_code == 429

        # usuário legítimo, mesmo IP, outra conta, credenciais corretas
        legit_user = {
            "id": str(uuid.uuid4()),
            "email": "legitimo@rvb.test",
            "tenant_id": str(uuid.uuid4()),
            "tenant_schema": "public",
            "role": "admin",
            "modules_enabled": ["epi"],
        }
        legit_svc = MagicMock()
        legit_svc.login.return_value = legit_user
        with patch(AUTH_SVC_PATH, return_value=legit_svc), \
             patch(_GET_REDIS, return_value=fake):
            resp = limited_client.post(
                "/api/auth/login",
                json={"email": "legitimo@rvb.test", "password": "correct"},
                environ_overrides={"REMOTE_ADDR": attacker_ip},
            )

        assert resp.status_code == 200


class TestSuccessResetsCounter:
    def test_success_resets_failure_count(self, monkeypatch):
        """client sem RATELIMIT (fixture padrão via app/client do conftest)
        não é necessário aqui — testamos só o comportamento de reset via a
        rota, com o limiter por IP desligado (TESTING default) para não
        misturar as duas defesas."""
        monkeypatch.setattr(lal, "MAX_FAILURES", 10)
        fake = _FakeRedis()
        email = "recupera@rvb.test"

        app = create_app("testing")
        client = app.test_client()

        with patch(AUTH_SVC_PATH, return_value=_failing_auth_service()), \
             patch(_GET_REDIS, return_value=fake):
            for _ in range(5):
                client.post("/api/auth/login", json={"email": email, "password": "wrong"})
            assert fake.store[lal._key(email)] == 5

        success_user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "tenant_id": str(uuid.uuid4()),
            "tenant_schema": "public",
            "role": "admin",
            "modules_enabled": ["epi"],
        }
        success_svc = MagicMock()
        success_svc.login.return_value = success_user
        with patch(AUTH_SVC_PATH, return_value=success_svc), \
             patch(_GET_REDIS, return_value=fake):
            resp = client.post(
                "/api/auth/login", json={"email": email, "password": "correct"}
            )
        assert resp.status_code == 200
        assert email not in fake.store or fake.store.get(lal._key(email), 0) == 0


class TestFailOpenViaRoute:
    def test_login_keeps_working_when_redis_unavailable(self, monkeypatch):
        """Redis indisponível (client que levanta em toda chamada) nunca
        pode impedir um login — nem bloquear por engano, nem quebrar a
        resposta de credenciais inválidas."""
        monkeypatch.setattr(lal, "MAX_FAILURES", 1)
        app = create_app("testing")
        client = app.test_client()

        with patch(AUTH_SVC_PATH, return_value=_failing_auth_service()), \
             patch(_GET_REDIS, return_value=_BrokenRedis()):
            codes = [
                client.post(
                    "/api/auth/login", json={"email": "x@test.com", "password": "wrong"}
                ).status_code
                for _ in range(5)
            ]
        # Sem Redis, nunca bloqueia por conta — toda tentativa segue até o
        # AuthService, que aqui sempre nega (401), nunca 429.
        assert all(c == 401 for c in codes), codes

        success_user = {
            "id": str(uuid.uuid4()),
            "email": "x@test.com",
            "tenant_id": str(uuid.uuid4()),
            "tenant_schema": "public",
            "role": "admin",
            "modules_enabled": ["epi"],
        }
        success_svc = MagicMock()
        success_svc.login.return_value = success_user
        with patch(AUTH_SVC_PATH, return_value=success_svc), \
             patch(_GET_REDIS, return_value=_BrokenRedis()):
            resp = client.post(
                "/api/auth/login", json={"email": "x@test.com", "password": "correct"}
            )
        assert resp.status_code == 200
