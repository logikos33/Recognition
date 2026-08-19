"""Issue #434 — `railway_start` e `nixpacks` apontavam para `landing-page/`.

Esse diretório NUNCA existiu no monorepo: a landing é `apps/landing` (ADR-0010).
O código procurava `dist/index.html` em três caminhos inexistentes, não achava,
tentava `npm ci` num diretório que não existe, e caía no placeholder — sem erro
que dissesse "o caminho está errado".

O teste fixa o que importa: o caminho candidato preferido tem de EXISTIR no
repositório. Um caminho de código que aponta para o vazio é o mesmo defeito da
semana — degradação sem sinal.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[5]


@pytest.fixture(scope="module")
def railway_start():
    spec = importlib.util.spec_from_file_location(
        "railway_start_landing", _RAIZ / "railway_start.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_apps_landing_existe_no_repo():
    assert (_RAIZ / "apps" / "landing" / "package.json").is_file(), (
        "a landing é apps/landing — se mudou de lugar, os candidatos do "
        "start_landing_page e o nixpacks.toml têm de mudar junto"
    )


def test_landing_page_solto_na_raiz_nao_existe():
    """Fixa a premissa: o caminho antigo é vazio, não uma alternativa válida."""
    assert not (_RAIZ / "landing-page").exists()


def test_primeiro_candidato_do_codigo_e_um_caminho_real(railway_start):
    fonte = pathlib.Path(railway_start.__file__).read_text(encoding="utf-8")
    bloco = re.search(r"candidates = \[(.*?)\]", fonte, re.DOTALL)
    assert bloco, "lista de candidatos não encontrada em start_landing_page"
    primeiro = bloco.group(1).strip().splitlines()[0]
    assert "'apps', 'landing'" in primeiro, (
        f"o primeiro candidato tem de ser o caminho que existe; é: {primeiro.strip()}"
    )


def test_nixpacks_aponta_para_apps_landing():
    conteudo = (_RAIZ / "nixpacks.toml").read_text(encoding="utf-8")
    assert "cd apps/landing" in conteudo
    assert "cd landing-page" not in conteudo, "diretório inexistente no build"
