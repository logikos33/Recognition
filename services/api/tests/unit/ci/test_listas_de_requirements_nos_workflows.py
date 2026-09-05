"""#753 — as listas de `requirements/` escritas À MÃO dentro do YAML.

Dois gates enumeram os requirements um por um, dentro do próprio workflow:

  ci.yml           job `lockfile-check`  → `for name in base api auth ...`
  security-scan.yml job `pip-audit`      → `strategy.matrix.requirements`

Lista escrita à mão é a forma silenciosa da mentira que a #421 ensinou: um
`requirements/novo.in` entra no repositório, ninguém lembra dos dois YAMLs, e
os dois gates seguem VERDES — sem nunca terem feito a pergunta sobre o arquivo
novo. Verde por ausência de pergunta, de novo.

⛔ NÃO extraí esses dois trechos para `scripts/ci/`: o do `lockfile-check` é um
driver de `pip-compile` (a política inteira dele é o `git diff --exit-code`
final) e o do `pip-audit` é uma matriz declarativa — em Python virariam script
que nenhum teste consegue exercitar sem rodar `pip-compile` por minutos. O que
era testável neles é o buraco acima, e é isso que este arquivo fecha.
"""
from __future__ import annotations

import pathlib
import re

import pytest
import yaml

_RAIZ = pathlib.Path(__file__).resolve().parents[5]
_WORKFLOWS = _RAIZ / ".github" / "workflows"
_REQUIREMENTS = _RAIZ / "requirements"


def descobertos(cobertos: set[str], no_disco: set[str]) -> set[str]:
    """Arquivos de requirements que existem e nenhum gate enumera."""
    return no_disco - cobertos


def _lista_do_lockfile() -> set[str]:
    doc = yaml.safe_load((_WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    passos = doc["jobs"]["lockfile-check"]["steps"]
    corpo = "\n".join(p.get("run", "") for p in passos if "pip-compile" in p.get("run", ""))
    achado = re.search(r"for name in ([^;\n]+)", corpo)
    assert achado, (
        "não encontrei o `for name in ...` do job lockfile-check em ci.yml. "
        "Se o laço mudou de forma, ajuste esta leitura — ⛔ não apague o teste: "
        "ele é o que impede a lista de virar cega."
    )
    return set(achado.group(1).split())


def _matriz_do_pip_audit() -> set[str]:
    doc = yaml.safe_load((_WORKFLOWS / "security-scan.yml").read_text(encoding="utf-8"))
    itens = doc["jobs"]["pip-audit"]["strategy"]["matrix"]["requirements"]
    return {i.removesuffix(".txt") for i in itens}


class TestOGateEnxergaTodoORequirements:
    def test_lockfile_check_recompila_TODO_requirements_in(self):
        no_disco = {p.stem for p in _REQUIREMENTS.glob("*.in")}
        faltando = descobertos(_lista_do_lockfile(), no_disco)
        assert not faltando, (
            f"requirements sem verificação de lock: {sorted(faltando)}. "
            f"Acrescente ao `for name in ...` do job lockfile-check em ci.yml — "
            f"sem isso o lock pode divergir do .in e o CI segue verde."
        )

    def test_pip_audit_audita_TODO_requirements_txt(self):
        no_disco = {p.stem for p in _REQUIREMENTS.glob("*.txt")}
        faltando = descobertos(_matriz_do_pip_audit(), no_disco)
        assert not faltando, (
            f"requirements nunca auditados por advisory: {sorted(faltando)}. "
            f"Acrescente à matriz do job pip-audit em security-scan.yml."
        )

    def test_os_gates_nao_enumeram_requirements_que_nao_existem(self):
        """Entrada morta na lista = passo que 'passa' sem arquivo nenhum."""
        no_disco_in = {p.stem for p in _REQUIREMENTS.glob("*.in")}
        no_disco_txt = {p.stem for p in _REQUIREMENTS.glob("*.txt")}
        assert not (_lista_do_lockfile() - no_disco_in)
        assert not (_matriz_do_pip_audit() - no_disco_txt)


class TestAComparacaoReprova:
    """Prova de que a comparação morde — sem isto os testes acima passariam
    até com `descobertos` devolvendo `set()` sempre."""

    def test_arquivo_novo_fora_da_lista_e_apontado(self):
        assert descobertos({"base", "api"}, {"base", "api", "novo"}) == {"novo"}

    def test_lista_completa_nao_aponta_nada(self):
        assert descobertos({"base", "api"}, {"base", "api"}) == set()

    @pytest.mark.parametrize("leitor", [_lista_do_lockfile, _matriz_do_pip_audit])
    def test_as_leituras_do_yaml_devolvem_algo(self, leitor):
        """Leitor que devolve vazio faria os testes acima passarem por engano."""
        assert len(leitor()) >= 5
