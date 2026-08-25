"""A polaridade tem de casar com o nome que o DETECTOR emite.

No catálogo global (`module_classes`) as duas colunas são nomes diferentes da
MESMA classe: `class_name` é o id técnico em inglês (`no_gloves`) e
`display_name` é o rótulo (`Sem Luvas`).

O detector emite o **rótulo**: a taxonomia do modelo vem das categorias do
export COCO, que vêm de `frame_annotations.class_name`, e ali o que está
gravado é o rótulo. Medido no DEV: 183 anotações com `class_name = 'Sem Luvas'`
e `class_id = 5`, que é `no_gloves` do catálogo global.

Casar só por `class_name` fazia `Sem Luvas` e `Sem Óculos` — que têm
`is_violation = TRUE` no catálogo desde a migration 009 — nunca baterem com
nada. Elas PARECIAM sem polaridade, e por pouco não foram recriadas como classe
custom do tenant: isso duplicaria a taxonomia e partiria as 183+95 anotações
existentes entre dois `class_id` diferentes.

Medido contra o banco do DEV, sobre as 12 classes que o modelo servido
(v10b-freeze) realmente emite:

    ANTES  → 5 indecididas: Capacete, Luvas, Sem Luvas, Óculos, Sem Óculos
    DEPOIS → 0 indecididas
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.infrastructure.database.repositories.alert_repository import AlertRepository

_TENANT = "63c219d8-fbef-4f3c-a7c9-058c742482e2"


def _repo_com_sql():
    repo = AlertRepository.__new__(AlertRepository)
    chamada = MagicMock(return_value=[])
    repo._execute = chamada  # type: ignore[method-assign]
    return repo, chamada


class TestOsDoisNomesDoCatalogoEntram:
    @pytest.mark.parametrize(
        "metodo", ["violation_class_names", "presence_class_names"]
    )
    def test_display_name_entra_na_busca(self, metodo):
        repo, chamada = _repo_com_sql()
        getattr(repo, metodo)(_TENANT, "epi")
        sql = chamada.call_args[0][0]
        assert "display_name" in sql, (
            "sem display_name, 'Sem Luvas' (que o detector emite) nunca casa "
            "com 'no_gloves' (que o catálogo guarda)"
        )
        assert "class_name" in sql, "o id técnico também tem de continuar valendo"

    @pytest.mark.parametrize(
        "metodo", ["violation_class_names", "presence_class_names"]
    )
    def test_classes_do_tenant_continuam_valendo(self, metodo):
        repo, chamada = _repo_com_sql()
        getattr(repo, metodo)(_TENANT, "epi")
        sql, params = chamada.call_args[0]
        assert "yolo_classes" in sql
        assert _TENANT in params

    def test_as_duas_polaridades_sao_opostas_no_sql(self):
        repo, chamada = _repo_com_sql()
        repo.violation_class_names(_TENANT, "epi")
        viol = chamada.call_args[0][0]
        repo.presence_class_names(_TENANT, "epi")
        pres = chamada.call_args[0][0]
        assert "is_violation IS TRUE" in viol
        assert "is_violation IS FALSE" in pres
        assert viol != pres

    def test_escopo_por_modulo_preservado(self):
        """Sem ele, classes de `fueling` (truck, plate) entram como
        conformidade de EPI — regressão que a docstring do método registra."""
        repo, chamada = _repo_com_sql()
        repo.violation_class_names(_TENANT, "epi")
        sql, params = chamada.call_args[0]
        assert sql.count("module_code = %s") == 2
        assert params == ("epi", _TENANT, "epi")

    def test_sem_modulo_nao_quebra_a_ordem_dos_params(self):
        repo, chamada = _repo_com_sql()
        repo.violation_class_names(_TENANT)
        sql, params = chamada.call_args[0]
        assert "module_code = %s" not in sql
        assert params == (_TENANT,)


class TestNaoRecriarClasseGlobalComoCustom:
    """Guard de intenção: `Sem Luvas`/`Sem Óculos` são do catálogo GLOBAL.

    Se alguém as recriar como classe custom do tenant, o `class_id` novo é
    namespaced (100000+) e as 183+95 anotações existentes (class_id 5 e 7)
    ficam órfãs de uma taxonomia que passa a ter dois nomes iguais.
    """

    def test_a_correcao_e_de_busca_nao_de_cadastro(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        migracoes = raiz.parent.parent / "infra" / "migrations"
        suspeitas = [
            p.name
            for p in migracoes.glob("*.sql")
            if "yolo_classes" in p.read_text(encoding="utf-8")
            and "Sem Luvas" in p.read_text(encoding="utf-8")
        ]
        assert not suspeitas, (
            f"migration criando 'Sem Luvas' em yolo_classes duplicaria a classe "
            f"global 5 (no_gloves): {suspeitas}"
        )
