"""
Suite de invariantes de segurança — /api/v1/edge/

Invariante 1 — auth obrigatória (toda rota /edge):
  Itera app.url_map via Blueprint registrado em app minimal; para CADA rota
  /api/v1/edge/ sem credenciais a resposta deve ser 4xx (nunca 2xx).
  - Rotas com auth por header (JWT/RS256): exige especificamente 401 ou 403.
  - Rotas com auth por corpo (/enroll): aceita qualquer 4xx (ex: 422 por
    ValidationError do Pydantic antes da verificação do token).

  Por que iterar url_map e não lista hardcoded?
  Um endpoint novo que esqueça auth não apareceria numa lista estática.
  Iterar garante cobertura automática de qualquer rota futura em edge_bp.

Invariante 2 — helpers cross-tenant reutilizáveis:
  Factories e assertions em _helpers_tenant.py.
  Toda task de endpoint /edge DEVE incluir ao menos um teste cross-tenant
  usando make_two_tenant_contexts + assert_response_only_contains_tenant.

Referências: constitution C-01 (multi-tenant), C-05 (segurança), C-07 (def. concluído).
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask import Flask

from app.api.v1.edge.routes import edge_bp

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

# Rotas que autenticam via corpo da requisição, não pelo header Authorization.
# Sem credencial no corpo → 4xx (geralmente 422 — ValidationError do Pydantic),
# não 401. Estão AQUI, não na ALLOWLIST: elas EXIGEM credencial.
_BODY_AUTH_ROUTES: frozenset[str] = frozenset({
    "/api/v1/edge/enroll",
})

# Rotas que legitimamente NÃO exigem nenhuma autenticação (endpoints públicos).
# Adicionar APENAS com justificativa explícita no comentário inline.
# Padrão = toda rota /edge exige auth.
_PUBLIC_ALLOWLIST: frozenset[str] = frozenset(
    # Vazio intencionalmente: nenhuma rota /edge é pública.
    # Exemplo de entrada futura (hipotética):
    #   "/api/v1/edge/version",  # [PUBLIC: retorna versão do agente sem dados sensíveis]
)

_SKIP_METHODS: frozenset[str] = frozenset({"HEAD", "OPTIONS"})

# UUID fixo para path params → IDs de teste estáveis no relatório pytest.
_DUMMY_UUID = "00000000-0000-0000-0000-000000000099"


def _substitute_path_params(rule_str: str) -> str:
    """Substitui <converter:param> e <param> por _DUMMY_UUID."""
    return re.sub(r"<[^>]+>", _DUMMY_UUID, rule_str)


def _collect_edge_route_params() -> list[pytest.param]:
    """Descobre rotas /api/v1/edge/ via url_map para parametrização.

    Usa app Flask minimal (só edge_bp) para evitar inicializar DB pool,
    Redis e SocketIO durante a coleta. O `client` fixture dos testes usa
    o app completo (create_app("testing")).
    """
    discovery_app = Flask(__name__)
    discovery_app.register_blueprint(edge_bp)

    params: list[pytest.param] = []
    for rule in discovery_app.url_map.iter_rules():
        if not rule.rule.startswith("/api/v1/edge/"):
            continue
        if rule.rule in _PUBLIC_ALLOWLIST:
            continue
        for method in sorted(rule.methods - _SKIP_METHODS):
            url = _substitute_path_params(rule.rule)
            body_auth = rule.rule in _BODY_AUTH_ROUTES
            params.append(
                pytest.param(
                    url,
                    method,
                    body_auth,
                    id=f"{method} {rule.rule}",
                )
            )
    return params


_EDGE_ROUTE_PARAMS = _collect_edge_route_params()


# ---------------------------------------------------------------------------
# Invariante 1 — auth obrigatória
# ---------------------------------------------------------------------------

class TestEdgeAuthInvariant:
    """Toda rota /api/v1/edge/* sem credencial → 4xx (nunca 2xx).

    Falhar aqui = endpoint público acidental em /edge = defeito de segurança (C-05).
    """

    @pytest.mark.parametrize("url,method,body_auth", _EDGE_ROUTE_PARAMS)
    def test_no_credentials_returns_4xx(
        self,
        client,
        url: str,
        method: str,
        body_auth: bool,
    ) -> None:
        """Requisição sem Authorization e sem token no corpo → sempre 4xx.

        - Auth por header (JWT/RS256bearer): exige 401 ou 403.
        - Auth por corpo (/enroll com enrollment_token): aceita qualquer 4xx;
          payload vazio causa 422 (Pydantic) antes mesmo da validação do token.
        """
        resp = client.open(url, method=method)
        status = resp.status_code

        assert status >= 400, (
            f"INVARIANTE QUEBRADA: {method} {url} retornou HTTP {status} "
            f"sem credenciais — endpoint público acidental? (C-05)"
        )

        if not body_auth:
            assert status in (401, 403), (
                f"INVARIANTE DE AUTH: {method} {url} retornou HTTP {status} "
                f"(esperado 401 ou 403 para rota com auth por header)"
            )


# ---------------------------------------------------------------------------
# Smoke tests dos helpers cross-tenant (_helpers_tenant.py)
# ---------------------------------------------------------------------------

class TestCrossTenantHelpers:
    """Verifica que os helpers de isolamento funcionam no app de teste.

    Objetivo: garantir que tasks de endpoint possam importar e usar
    make_two_tenant_contexts + assert_response_only_contains_tenant sem surpresas.
    """

    def test_make_user_jwt_token_is_accepted_by_jwt_protected_route(
        self, app, client
    ) -> None:
        """make_user_jwt gera token válido aceito por rotas com @jwt_required_custom."""
        from tests.security._helpers_tenant import make_user_jwt

        tenant_id = uuid4()
        token = make_user_jwt(app, tenant_id, role="admin")

        mock_repo = MagicMock()
        mock_repo.list_sites.return_value = []

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            resp = client.get(
                "/api/v1/edge/sites",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200, (
            f"make_user_jwt produziu token inválido (status={resp.status_code})"
        )

    def test_make_two_tenant_contexts_returns_distinct_tenants(self, app) -> None:
        """make_two_tenant_contexts garante tenant_id, site_id e jwt_token distintos."""
        from tests.security._helpers_tenant import make_two_tenant_contexts

        ctx_a, ctx_b = make_two_tenant_contexts(app)

        assert ctx_a.tenant_id != ctx_b.tenant_id
        assert ctx_a.site_id != ctx_b.site_id
        assert ctx_a.jwt_token != ctx_b.jwt_token

    def test_assert_response_only_contains_tenant_passes_for_own_data(self) -> None:
        """assert_response_only_contains_tenant não falha quando dados são do tenant certo."""
        from tests.security._helpers_tenant import assert_response_only_contains_tenant

        tid = "aaaaaaaa-0000-0000-0000-000000000001"
        resp_json = {
            "status": "success",
            "data": {
                "sites": [
                    {"id": "s1", "tenant_id": tid, "name": "Site A"},
                    {"id": "s2", "tenant_id": tid, "name": "Site B"},
                ]
            },
        }
        assert_response_only_contains_tenant(resp_json, tid)

    def test_assert_response_only_contains_tenant_fails_on_cross_tenant_leak(
        self,
    ) -> None:
        """assert_response_only_contains_tenant levanta AssertionError ao detectar leak."""
        from tests.security._helpers_tenant import assert_response_only_contains_tenant

        tid_a = "aaaaaaaa-0000-0000-0000-000000000001"
        tid_b = "bbbbbbbb-0000-0000-0000-000000000002"
        resp_json = {
            "status": "success",
            "data": {
                "sites": [
                    {"id": "s1", "tenant_id": tid_a},
                    {"id": "s2", "tenant_id": tid_b},  # vazamento cross-tenant!
                ]
            },
        }
        with pytest.raises(AssertionError, match="Cross-tenant leak"):
            assert_response_only_contains_tenant(resp_json, tid_a)

    def test_make_device_token_produces_valid_rs256_structure(self) -> None:
        """make_device_token retorna (token, public_key_pem) com formato RS256 válido."""
        from tests.security._helpers_tenant import make_device_token
        import jwt as pyjwt

        tenant_id = uuid4()
        site_id = uuid4()
        token_str, public_pem = make_device_token(tenant_id, site_id)

        assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")

        payload = pyjwt.decode(
            token_str,
            public_pem,
            algorithms=["RS256"],
        )
        assert str(payload["tenant_id"]) == str(tenant_id)
        assert str(payload["site_id"]) == str(site_id)
        assert "device_id" in payload


# ---------------------------------------------------------------------------
# Cross-tenant: tenant_b não vê sites do tenant_a
# ---------------------------------------------------------------------------

class TestEdgeCrossTenantIsolation:
    """C-01: tenant_b nunca recebe dados de tenant_a nas rotas /edge.

    Serve também como exemplo canônico de uso dos helpers para tasks futuras.
    """

    def test_list_sites_tenant_b_sees_only_own_sites(self, client, app) -> None:
        """GET /api/v1/edge/sites: tenant_b recebe lista vazia quando tenant_a tem sites."""
        from tests.security._helpers_tenant import (
            assert_response_only_contains_tenant,
            make_two_tenant_contexts,
        )
        from datetime import datetime, timezone

        ctx_a, ctx_b = make_two_tenant_contexts(app)

        site_a = {
            "id": str(uuid4()),
            "tenant_id": str(ctx_a.tenant_id),
            "name": "Site Tenant A",
            "description": None,
            "location": None,
            "deployment_mode": "edge",
            "status": "active",
            "created_at": str(datetime(2026, 6, 1, tzinfo=timezone.utc)),
            "created_by": None,
        }

        mock_repo = MagicMock()

        def _list_sites(tid: str) -> list:
            return [site_a] if tid == str(ctx_a.tenant_id) else []

        mock_repo.list_sites.side_effect = _list_sites

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            resp_b = client.get(
                "/api/v1/edge/sites",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert resp_b.status_code == 200
        assert_response_only_contains_tenant(resp_b.get_json(), ctx_b.tenant_id)
        data = resp_b.get_json()["data"]["sites"]
        assert data == [], "tenant_b NÃO deve receber sites de tenant_a"

    def test_enrollment_token_for_site_of_other_tenant_returns_404(
        self, client, app
    ) -> None:
        """POST .../enrollment-tokens para site de outro tenant → 404 (C-01)."""
        from tests.security._helpers_tenant import make_two_tenant_contexts

        ctx_a, ctx_b = make_two_tenant_contexts(app)
        site_id_a = ctx_a.site_id

        mock_repo = MagicMock()
        # tenant_b não enxerga o site de tenant_a
        mock_repo.get_site_by_id.return_value = None

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            resp = client.post(
                f"/api/v1/edge/sites/{site_id_a}/enrollment-tokens",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert resp.status_code == 404
        mock_repo.create_enrollment_token.assert_not_called()
        mock_repo.get_site_by_id.assert_called_once_with(
            str(site_id_a), str(ctx_b.tenant_id)
        )
