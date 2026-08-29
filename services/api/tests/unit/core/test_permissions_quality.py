"""Chaves de Qualidade — nome-como-contrato, testado.

A lição do #445: quando o NOME é o contrato entre duas camadas, ele precisa de
teste. Uma chave de permissão é exatamente isso — o front escreve
`can('quality:write')` e o backend decide por essa string. Se as duas divergirem,
nada estoura: `can()` devolve False para chave inexistente, o controle some da
tela de todo mundo MENOS do superadmin (que passa por cima de tudo) — e quem
testa, testando como superadmin, nunca vê o problema.

Foi por isso que a tela de retrabalho nasceu sem gate: `quality:*` não existia.
"""
import re
from pathlib import Path

import pytest

from app.core.permissions import (
    PERMISSION_REGISTRY,
    all_permission_keys,
    permissions_for_role,
)

# core → unit → tests → api → services → RAIZ  (seis níveis)
RAIZ = Path(__file__).resolve().parents[5]
FRONT_NOVO = RAIZ / "apps" / "frontend" / "src" / "app"

CHAVES_QUALIDADE = ("quality:read", "quality:write")


class TestChavesExistem:
    def test_as_duas_chaves_estao_no_registry(self):
        for k in CHAVES_QUALIDADE:
            assert k in PERMISSION_REGISTRY, f"{k} não existe no registry"
            assert k in all_permission_keys()

    def test_seguem_o_padrao_de_counting(self):
        """Mesma forma que `counting:*` — módulo declarado, textos em pt-BR."""
        for k in CHAVES_QUALIDADE:
            e = PERMISSION_REGISTRY[k]
            assert e.get("module") == "quality", f"{k} sem module='quality'"
            assert e.get("label", "").strip(), f"{k} sem label"
            assert e.get("description", "").strip(), f"{k} sem description"

    def test_a_escrita_e_mais_restrita_que_a_leitura(self):
        """Quem escreve é subconjunto de quem lê — o contrário é buraco."""
        for papel in ("superadmin", "admin", "operator", "analyst", "trainer", "viewer"):
            perms = set(permissions_for_role(papel))
            if "quality:write" in perms:
                assert "quality:read" in perms, (
                    f"{papel} pode escrever em Qualidade e não pode ler"
                )

    @pytest.mark.parametrize(
        ("papel", "le", "escreve"),
        [
            ("superadmin", True, True),
            ("admin", True, True),
            ("operator", True, True),   # é quem conclui retrabalho na bancada
            ("analyst", True, False),
            ("viewer", True, False),
            ("trainer", False, False),  # persona do Estúdio; Qualidade não é dele
        ],
    )
    def test_matriz_por_papel(self, papel, le, escreve):
        perms = set(permissions_for_role(papel))
        assert ("quality:read" in perms) is le
        assert ("quality:write" in perms) is escreve


class TestOFrontUsaSoChaveQueExiste:
    """A ponte entre as camadas: toda `can('...')` do front novo tem de existir.

    O teste do front já faz o mesmo cruzamento do lado dele. Este existe do lado
    do BACKEND porque quem mexe no registry mexe aqui — e quem apaga uma chave
    daqui não roda a suíte do front.
    """

    def _chaves_do_front(self) -> set[str]:
        chaves: set[str] = set()
        # Sem `skip`: um teste que se pula sozinho vira verde falso, e este é
        # justamente o que liga as duas camadas. Se o caminho quebrar, tem de
        # falhar alto.
        assert FRONT_NOVO.is_dir(), f"front novo não encontrado em {FRONT_NOVO}"
        for arq in FRONT_NOVO.rglob("*.ts*"):
            if arq.name.endswith((".test.ts", ".test.tsx")):
                continue
            texto = arq.read_text(encoding="utf-8", errors="ignore")
            chaves |= set(re.findall(r"can\(\s*['\"]([a-z_]+:[a-z_]+)['\"]", texto))
            chaves |= set(re.findall(r"permissao:\s*'([a-z_]+:[a-z_]+)'", texto))
        return chaves

    def test_nenhuma_chave_do_front_falta_no_registry(self):
        usadas = self._chaves_do_front()
        assert usadas, "varredura não achou chave nenhuma — o regex quebrou"
        faltando = sorted(k for k in usadas if k not in PERMISSION_REGISTRY)
        assert not faltando, (
            "o front novo usa chave que o backend não conhece — o controle some "
            f"em silêncio para todos menos o superadmin: {faltando}"
        )
