"""#753 — o gate que guarda os workflows não tinha um único teste.

Contexto: `check_workflow_hygiene.py` nasceu de dois defeitos MEDIDOS —
`security-scan.yml` com chave YAML duplicada ficou 85 runs sem executar
(o GitHub recusa o arquivo inteiro: run `failure`, zero jobs, zero log), e
`Install Playwright browsers` queimou 6h de runner por falta de
`timeout-minutes`. Depois ganhou um terceiro: `continue-on-error` de JOB, que
faz o WORKFLOW dizer `success` com o job em `failure`.

Três regras de segurança de CI que nenhum teste executava. A D-192 diz que gate
de CI mora em script testável; o script existia, o teste não. Estes testes
fixam a única propriedade que importa num gate: **ele REPROVA o caso ruim**.

Prova de que mordem (mutações que matam cada um):
  - `if timeout is None` -> `if False`                      → mata o de timeout
  - `job.get("continue-on-error") in (True,)` -> `in ()`    → mata o de COE
  - trocar `_StrictLoader` por `yaml.SafeLoader`            → mata o de duplicata
  - `elif timeout > MAX_MINUTES` -> `elif False`            → mata o do teto
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[5]
_GATE = _RAIZ / "scripts" / "ci" / "check_workflow_hygiene.py"

sys.path.insert(0, str(_GATE.parent))
from check_workflow_hygiene import MAX_MINUTES, checar  # noqa: E402

SADIO = """\
name: Exemplo
on: [push]
jobs:
  build:
    name: Build
    timeout-minutes: 10
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""


def _dir(tmp_path: pathlib.Path, **arquivos: str) -> pathlib.Path:
    d = tmp_path / "workflows"
    d.mkdir(exist_ok=True)
    for nome, conteudo in arquivos.items():
        (d / nome.replace("__", ".")).write_text(conteudo, encoding="utf-8")
    return d


class TestReprovaOCasoRuim:
    def test_chave_duplicada_reprova(self, tmp_path):
        """O defeito de 18/08: `working-directory` repetido no mesmo step.

        ⚠️ `yaml.safe_load` NÃO reclama — fica com a última e segue em frente.
        O GitHub recusa o arquivo inteiro. Se este teste ficar verde com o
        SafeLoader padrão, o gate voltou a ser decorativo.
        """
        ruim = SADIO.replace(
            "      - run: echo ok\n",
            "      - run: echo ok\n        working-directory: a\n        working-directory: b\n",
        )
        erros, _, _ = checar(_dir(tmp_path, ruim__yml=ruim))
        assert erros, "chave duplicada passou — o GitHub recusaria este arquivo"
        assert "working-directory" in erros[0] and "repetida" in erros[0]

    def test_job_sem_timeout_reprova(self, tmp_path):
        """Sem `timeout-minutes` o default do GitHub é 360min — 6h por travada."""
        erros, _, _ = checar(_dir(tmp_path, x__yml=SADIO.replace("    timeout-minutes: 10\n", "")))
        assert erros and "sem `timeout-minutes`" in erros[0]

    def test_timeout_acima_do_teto_reprova(self, tmp_path):
        """Teto de sanidade: 360min declarado explicitamente é o mesmo dano."""
        ruim = SADIO.replace("timeout-minutes: 10", f"timeout-minutes: {MAX_MINUTES + 1}")
        erros, _, _ = checar(_dir(tmp_path, x__yml=ruim))
        assert erros and "teto" in erros[0]

    @pytest.mark.parametrize("valor", ["0", "-5", "abc"])
    def test_timeout_invalido_reprova(self, tmp_path, valor):
        ruim = SADIO.replace("timeout-minutes: 10", f"timeout-minutes: {valor}")
        erros, _, _ = checar(_dir(tmp_path, x__yml=ruim))
        assert erros and "inválido" in erros[0]

    def test_continue_on_error_de_JOB_reprova(self, tmp_path):
        """A mentira da #421: workflow `success` com job em `failure`."""
        ruim = SADIO.replace(
            "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    continue-on-error: true\n"
        )
        erros, _, _ = checar(_dir(tmp_path, x__yml=ruim))
        assert erros and "continue-on-error" in erros[0]

    def test_yaml_quebrado_reprova_em_vez_de_ignorar(self, tmp_path):
        erros, _, _ = checar(_dir(tmp_path, x__yml="jobs: [isto: {nao: fecha\n"))
        assert erros

    def test_arquivo_sem_bloco_jobs_reprova(self, tmp_path):
        erros, _, _ = checar(_dir(tmp_path, x__yml="name: nada\non: [push]\n"))
        assert erros and "jobs" in erros[0]

    def test_diretorio_vazio_reprova_em_vez_de_passar_por_omissao(self, tmp_path):
        """Zero workflows encontrados = a pergunta não foi feita, ⛔ não 'está tudo bem'."""
        d = tmp_path / "workflows"
        d.mkdir()
        erros, _, _ = checar(d)
        assert erros and "Nenhum workflow" in erros[0]


class TestAceitaOCasoBom:
    def test_workflow_sadio_passa(self, tmp_path):
        erros, arquivos, jobs = checar(_dir(tmp_path, ok__yml=SADIO))
        assert erros == [] and arquivos == 1 and jobs == 1

    def test_continue_on_error_de_STEP_e_permitido(self, tmp_path):
        """A saída honesta para "avisar sem barrar" — o bandit usa isso hoje."""
        bom = SADIO.replace(
            "      - run: echo ok\n", "      - run: echo ok\n        continue-on-error: true\n"
        )
        erros, _, _ = checar(_dir(tmp_path, ok__yml=bom))
        assert erros == []

    def test_job_reutilizavel_nao_exige_timeout(self, tmp_path):
        reutilizavel = "name: R\non: [push]\njobs:\n  chamado:\n    uses: ./.github/workflows/outro.yml\n"
        erros, _, _ = checar(_dir(tmp_path, r__yml=reutilizavel))
        assert erros == []

    def test_extensao_yaml_tambem_e_lida(self, tmp_path):
        """.yaml é workflow como qualquer outro — pular seria buraco silencioso."""
        erros, arquivos, _ = checar(
            _dir(tmp_path, x__yaml=SADIO.replace("timeout-minutes: 10\n", ""))
        )
        assert erros and arquivos == 1


class TestFronteiraDoProcesso:
    """O CI chama por linha de comando — o teste cruza essa fronteira."""

    def test_repo_real_passa_com_saida_zero(self):
        p = subprocess.run(
            [sys.executable, str(_GATE)], capture_output=True, text=True, timeout=120
        )
        assert p.returncode == 0, p.stdout + p.stderr
        assert "OK" in p.stdout
