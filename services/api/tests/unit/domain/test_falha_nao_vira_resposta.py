"""Falha de leitura/escrita não pode devolver o valor que significa "tudo bem".

Três casos da mesma família, todos achados por varredura e todos com o mesmo
formato: o `except` devolvia um valor LEGÍTIMO do domínio, e o consumidor a
jusante não tinha como distinguir.

  · overrides de permissão -> `[]` = "nenhum deny"  (falha ABERTA em autorização)
  · fila de verificação    -> `[]` = "fila vazia"   (operador vai embora)
  · contagem               -> warning = "gravei"    (tabela com 0 linhas)
"""
from unittest.mock import MagicMock

import pytest

from app.domain.services.counting_service import CountingService
from app.domain.services.permission_service import PermissionService
from app.domain.services.verification_service import VerificationService


class TestPermissaoNaoFalhaAberta:
    """Um deny que some é uma permissão revogada que volta a valer."""

    def _servico(self, repo_overrides):
        svc = PermissionService.__new__(PermissionService)
        svc._overrides = repo_overrides
        svc._custom_roles = MagicMock()
        return svc

    def test_erro_de_banco_sobe_em_vez_de_virar_lista_vazia(self):
        repo = MagicMock()
        repo.list_by_user.side_effect = RuntimeError("banco caiu")

        with pytest.raises(RuntimeError):
            self._servico(repo)._override_rows({"id": "u1"})

    def test_usuario_sem_id_continua_devolvendo_vazio(self):
        """Não é falha: é ausência de usuário, e aí [] é a resposta certa."""
        repo = MagicMock()
        assert self._servico(repo)._override_rows({}) == []
        repo.list_by_user.assert_not_called()

    def test_leitura_boa_devolve_os_overrides(self):
        repo = MagicMock()
        repo.list_by_user.return_value = [{"permission_key": "x", "allow": False}]
        assert self._servico(repo)._override_rows({"id": "u1"}) == [
            {"permission_key": "x", "allow": False}
        ]


class TestFilaDeVerificacaoNaoMenteVazia:
    def test_erro_de_banco_sobe_para_a_rota_devolver_500(self, monkeypatch):
        from app.domain.services import verification_service as mod

        pool = MagicMock()
        pool.get_connection.side_effect = RuntimeError("banco caiu")
        monkeypatch.setattr(mod, "_get_pool", lambda: pool)

        with pytest.raises(RuntimeError):
            VerificationService().get_human_queue(tenant_id="t1")

    def test_badge_tambem_nao_devolve_zero_em_falha(self, monkeypatch):
        from app.domain.services import verification_service as mod

        pool = MagicMock()
        pool.get_connection.side_effect = RuntimeError("banco caiu")
        monkeypatch.setattr(mod, "_get_pool", lambda: pool)

        with pytest.raises(RuntimeError):
            VerificationService().get_queue_count(tenant_id="t1")

    def test_sem_pool_continua_devolvendo_vazio(self, monkeypatch):
        """Pool ausente é ambiente sem banco, não erro de consulta."""
        from app.domain.services import verification_service as mod

        monkeypatch.setattr(mod, "_get_pool", lambda: None)
        assert VerificationService().get_human_queue(tenant_id="t1") == []


class TestContagemNaoEngoleFalhaDeGravacao:
    def test_falha_de_insert_sobe(self):
        repo = MagicMock()
        repo.upsert_event.side_effect = RuntimeError("not-null violation")
        svc = CountingService.__new__(CountingService)
        svc._repo = repo

        with pytest.raises(RuntimeError):
            svc.record_detection("s1", 42, "caixa", 0.9)

    def test_gravacao_boa_nao_levanta(self):
        repo = MagicMock()
        svc = CountingService.__new__(CountingService)
        svc._repo = repo
        svc.record_detection("s1", 42, "caixa", 0.9)
        repo.upsert_event.assert_called_once_with("s1", 42, "caixa", 0.9)

    def test_o_insert_deriva_o_tenant_da_sessao(self):
        """`tenant_id` é NOT NULL sem default — o INSERT antigo nem o citava."""
        from app.infrastructure.database.repositories.counting_repository import (
            CountingRepository,
        )

        repo = CountingRepository.__new__(CountingRepository)
        mutation = MagicMock(return_value=None)
        repo._execute_mutation = mutation  # type: ignore[method-assign]

        repo.upsert_event("s1", 42, "caixa", 0.9)

        sql, _params = mutation.call_args[0]
        assert "tenant_id" in sql, "sem tenant_id o INSERT viola NOT NULL sempre"
        assert "FROM counting_sessions" in sql, "o tenant tem de vir da sessão"
        assert "cs.site_id" not in sql, "counting_sessions não tem site_id"
