"""A zona EPI aceitava só a taxonomia de demonstração — sexta camada COCO.

A ADR-0067 exige que a violação só nasça **na zona onde o EPI é exigido**. Mas
`EpiZoneOperation.validate_config` validava `watch_classes` contra
`EpiClass` — um `StrEnum` fixo com
`helmet/no_helmet/vest/no_vest/gloves/no_gloves/safety_glasses/no_safety_glasses`
— e o `config_schema` ainda publicava esse mesmo enum para a tela.

Nenhum desses oito nomes existe no cadastro do RVB. Medido contra o banco do
DEV antes da correção:

    ['Sem protetor de ouvido']   → "classe inválida: não pertence ao módulo epi"
    ['Sem Luvas']                → idem
    ['Uso incorreto de mascara'] → idem
    ['no_helmet']                → aceita

Ou seja: **o admin do cliente não conseguia configurar zona nenhuma**, e o
requisito de zona da ADR-0067 era inalcançável.

A fonte das classes válidas é o cadastro (catálogo global ∪ classes do tenant),
a mesma da polaridade (ADR-0065).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.domain.services.operations.canonical.epi_zone import (
    _VALID_EPI_CLASSES,
    EpiZoneOperation,
)

_TENANT = "63c219d8-fbef-4f3c-a7c9-058c742482e2"
_ZONA = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]

#: O que o banco do DEV devolve para o RVB.
_PRESENCA = ["protetor auditivo", "mascara", "botas", "luvas", "óculos"]
_VIOLACAO = ["sem protetor de ouvido", "sem mascara", "sem luvas", "sem óculos",
             "uso incorreto de mascara"]


def _com_cadastro(presenca=_PRESENCA, violacao=_VIOLACAO):
    repo = MagicMock()
    repo.presence_class_names.return_value = presenca
    repo.violation_class_names.return_value = violacao
    pool = MagicMock()
    return (
        patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=pool,
        ),
        patch(
            "app.infrastructure.database.repositories.alert_repository."
            "AlertRepository",
            return_value=repo,
        ),
    )


def _valida(classes, tenant_id=None):
    cfg = {"zone_points": _ZONA, "watch_classes": classes}
    return EpiZoneOperation(cfg, tenant_id=tenant_id).validate_config(cfg)


class TestClasseDoClienteEhAceita:
    def test_classe_de_ausencia_do_rvb_passa(self):
        p1, p2 = _com_cadastro()
        with p1, p2:
            assert _valida(["Sem protetor de ouvido"], _TENANT) == []

    def test_todas_as_de_ausencia_do_rvb_passam(self):
        p1, p2 = _com_cadastro()
        with p1, p2:
            erros = _valida(
                ["Sem Luvas", "Sem Óculos", "Uso incorreto de mascara"], _TENANT
            )
        assert erros == []

    def test_case_insensitive(self):
        """O cadastro guarda em lower; o admin digita como quiser."""
        p1, p2 = _com_cadastro()
        with p1, p2:
            assert _valida(["SEM MASCARA"], _TENANT) == []

    def test_nome_tecnico_do_catalogo_global_continua_valendo(self):
        """Retrocompat: quem já tinha zona com `no_helmet` não quebra."""
        p1, p2 = _com_cadastro()
        with p1, p2:
            assert _valida(["no_helmet"], _TENANT) == []


class TestNaoVirouPermissiva:
    def test_classe_inexistente_continua_recusada(self):
        p1, p2 = _com_cadastro()
        with p1, p2:
            erros = _valida(["Classe Que Nao Existe"], _TENANT)
        assert erros and "classe inválida" in erros[0]

    def test_watch_classes_vazio_continua_recusado(self):
        p1, p2 = _com_cadastro()
        with p1, p2:
            erros = _valida([], _TENANT)
        assert erros and "obrigatório" in erros[0]

    def test_zona_com_menos_de_tres_pontos_continua_recusada(self):
        cfg = {"zone_points": [[0.1, 0.1]], "watch_classes": ["no_helmet"]}
        erros = EpiZoneOperation(cfg).validate_config(cfg)
        assert any("3 pontos" in e for e in erros)


class TestFalhaNaoTravaAConfiguracao:
    def test_sem_tenant_cai_na_lista_historica(self):
        """Caller antigo e teste continuam funcionando."""
        assert _valida(["no_helmet"]) == []
        assert _valida(["Sem Luvas"]) != []

    def test_erro_de_banco_nao_vira_nada_e_valido(self, caplog):
        """Falha de leitura travaria a configuração inteira — cai na lista
        histórica e AVISA, em vez de recusar tudo."""
        import logging

        pool = MagicMock()
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=pool,
        ), patch(
            "app.infrastructure.database.repositories.alert_repository."
            "AlertRepository",
            side_effect=RuntimeError("banco caiu"),
        ), caplog.at_level(logging.WARNING):
            erros = _valida(["no_helmet"], _TENANT)
        assert erros == []
        assert "epi_zone_classes_do_cadastro_falhou" in caplog.text

    def test_sem_pool_cai_na_lista_historica(self):
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=None,
        ):
            assert _valida(["no_helmet"], _TENANT) == []


class TestOEsquemaNaoPublicaMaisOEnumFixo:
    def test_schema_sem_enum_de_classe(self):
        """Esquema estático não consegue listar classe que muda por cliente.

        Quem preenche a tela é GET /api/modules/epi/classes."""
        esquema = EpiZoneOperation.config_schema
        watch = esquema["properties"]["watch_classes"]["items"]
        assert "enum" not in watch, (
            "enum estático de classe volta a esconder a taxonomia do cliente"
        )
        assert watch["type"] == "string"

    def test_a_lista_historica_ainda_existe_como_ultimo_recurso(self):
        assert "no_helmet" in _VALID_EPI_CLASSES
