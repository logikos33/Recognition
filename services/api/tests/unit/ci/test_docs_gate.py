"""#753 — o `Docs gate` reprova PR de todo mundo e não tinha um único teste.

Ele nasceu de seis relatos falsos numa semana (CLAUDE.md descrevendo `backend/`
e 13 microserviços inexistentes; evidência dita "cloud-first" já superseded;
classe fantasma "Sem Capacete" que nunca existiu no banco; duas ADR-0043; a
0057 citada mas ausente). Ver docs/decisions/PROCEDENCIA_DE_RELATOS.md.

Um gate de procedência que parasse de reprovar seria descoberto do pior jeito
possível: pelo sétimo relato falso passando. Estes testes montam uma árvore de
docs que VIOLA cada regra e provam que o gate reprova.

Prova de que mordem (mutações que matam cada uma):
  regra 1 `if len(group) > 1` -> `if False`
  regra 2 `not in VALID_STATUS` -> `in VALID_STATUS`
  regra 3 remover o laço do buraco de sequência
  regra 4 `cited & superseded_nums` -> `set()`
  regra 5 `!=` -> `==` na comparação de número interno
  regra 6 `len({...}) > 1` -> `> 2`
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[5]
_GATE = _RAIZ / "scripts" / "ci" / "check_docs_gate.py"

sys.path.insert(0, str(_GATE.parent))
from check_docs_gate import check  # noqa: E402


def _adr(raiz: pathlib.Path, arquivo: str, *, titulo_num: int, status: str = "Aceito") -> None:
    (raiz / "docs" / "decisions" / "adr" / arquivo).write_text(
        f"# ADR-{titulo_num:04d} — Exemplo\n\n**Status:** {status}\n\nCorpo.\n",
        encoding="utf-8",
    )


@pytest.fixture
def raiz(tmp_path: pathlib.Path) -> pathlib.Path:
    """Árvore de docs forjada e CONSISTENTE — ponto de partida verde."""
    (tmp_path / "docs" / "decisions" / "adr").mkdir(parents=True)
    _adr(tmp_path, "0001-primeiro.md", titulo_num=1)
    _adr(tmp_path, "0002-segundo.md", titulo_num=2)
    (tmp_path / "CLAUDE.md").write_text("Projeto. Ver ADR-0001.\n", encoding="utf-8")
    return tmp_path


def _problemas(raiz: pathlib.Path) -> str:
    return " | ".join(f"{onde}: {oq}" for onde, oq in check(raiz))


class TestReprovaOCasoRuim:
    def test_regra1_numero_de_ADR_duplicado_reprova(self, raiz):
        """As duas ADR-0043 do relato original."""
        _adr(raiz, "0002-gemeo.md", titulo_num=2)
        assert "ADR-0002 duplicado" in _problemas(raiz)

    @pytest.mark.parametrize("status", ["Talvez", "", "Em análise"])
    def test_regra2_status_invalido_ou_ausente_reprova(self, raiz, status):
        _adr(raiz, "0003-terceiro.md", titulo_num=3, status=status)
        assert "Status inválido ou ausente" in _problemas(raiz)

    def test_regra3_buraco_na_sequencia_reprova(self, raiz):
        """A ADR-0057 citada mas ausente. Número queimado tem de ser DECLARADO."""
        _adr(raiz, "0004-quarto.md", titulo_num=4)  # pula o 0003
        assert "ADR-0003 ausente na sequência" in _problemas(raiz)

    def test_regra4_CLAUDE_md_citando_ADR_superseded_reprova(self, raiz):
        """Foi exatamente assim que a evidência 'cloud-first' já superseded
        continuou sendo citada como verdade corrente."""
        _adr(raiz, "0001-primeiro.md", titulo_num=1, status="Superseded")
        assert "cita ADR-0001, que está Superseded" in _problemas(raiz)

    def test_regra4_pega_supersede_declarada_so_no_CORPO(self, raiz):
        """Sem isto, bastaria não mexer no Status para a citação morta passar."""
        (raiz / "docs" / "decisions" / "adr" / "0001-primeiro.md").write_text(
            "# ADR-0001 — Exemplo\n\n**Status:** Aceito\n\n> superseded por ADR-0002\n",
            encoding="utf-8",
        )
        assert "cita ADR-0001, que está Superseded" in _problemas(raiz)

    def test_regra5_titulo_interno_divergente_do_arquivo_reprova(self, raiz):
        _adr(raiz, "0003-terceiro.md", titulo_num=7)
        assert "título interno diz ADR-0007 mas o arquivo é 0003" in _problemas(raiz)

    def test_regra5_sem_titulo_interno_reprova(self, raiz):
        (raiz / "docs" / "decisions" / "adr" / "0003-sem-titulo.md").write_text(
            "Sem cabeçalho.\n\n**Status:** Aceito\n", encoding="utf-8"
        )
        assert "sem título interno" in _problemas(raiz)

    def test_regra6_taxonomia_RVB_divergente_entre_documentos_reprova(self, raiz):
        """A divergência entre docs foi o que pôs a classe fantasma
        'Sem Capacete' em três rodadas de anotação."""
        bloco = "<!-- RVB-EPI-CLASSES:start -->\n{itens}\n<!-- RVB-EPI-CLASSES:end -->\n"
        (raiz / "a.md").write_text(bloco.format(itens="- Luva\n- Óculos"), encoding="utf-8")
        (raiz / "b.md").write_text(
            bloco.format(itens="- Luva\n- Óculos\n- Sem Capacete"), encoding="utf-8"
        )
        p = _problemas(raiz)
        assert "taxonomia RVB" in p and "diverge" in p and "sem capacete" in p


class TestAceitaOCasoBom:
    def test_arvore_consistente_passa(self, raiz):
        assert check(raiz) == []

    def test_supersede_PARCIAL_nao_conta_como_superseded(self, raiz):
        """"Parcialmente superseded por ADR-X" continua valendo — citar não é erro."""
        (raiz / "docs" / "decisions" / "adr" / "0001-primeiro.md").write_text(
            "# ADR-0001 — Exemplo\n\n**Status:** Aceito\n\nParcialmente superseded por ADR-0002.\n",
            encoding="utf-8",
        )
        assert check(raiz) == []

    def test_placeholder_Reservado_preenche_o_buraco(self, raiz):
        """A saída declarada para número queimado — se ela não funcionar, o
        conselho impresso pelo próprio gate é mentira."""
        _adr(raiz, "0003-reservado.md", titulo_num=3, status="Reservado")
        _adr(raiz, "0004-quarto.md", titulo_num=4)
        assert check(raiz) == []

    def test_taxonomia_IGUAL_em_varios_documentos_passa(self, raiz):
        bloco = "<!-- RVB-EPI-CLASSES:start -->\n- Luva\n- Óculos\n<!-- RVB-EPI-CLASSES:end -->\n"
        (raiz / "a.md").write_text(bloco, encoding="utf-8")
        (raiz / "b.md").write_text(bloco, encoding="utf-8")
        assert check(raiz) == []

    def test_convencao_alternativa_de_status_e_titulo_e_aceita(self, raiz):
        """`## Status` (Nygard) com o valor na linha seguinte e `# ADR 0003`
        existem no repo — reprovar por convenção seria falso positivo."""
        (raiz / "docs" / "decisions" / "adr" / "0003-nygard.md").write_text(
            "# ADR 0003 — Exemplo\n\n## Status\n\nAceita\n\nCorpo.\n", encoding="utf-8"
        )
        assert check(raiz) == []

    def test_template_0000_e_nao_ADR_sao_ignorados(self, raiz):
        _adr(raiz, "0000-template.md", titulo_num=0)
        (raiz / "docs" / "decisions" / "adr" / "RECONCILIACAO_X.md").write_text("qualquer\n")
        assert check(raiz) == []


class TestFronteiraDoProcesso:
    def test_repo_real_passa_com_saida_zero(self):
        p = subprocess.run(
            [sys.executable, str(_GATE)], capture_output=True, text=True, timeout=180
        )
        assert p.returncode == 0, p.stdout + p.stderr
        assert "PASSED" in p.stdout

    def test_report_only_imprime_mas_nao_reprova(self, tmp_path):
        """A porta de escape documentada tem de existir de verdade."""
        p = subprocess.run(
            [sys.executable, str(_GATE), "--report-only"],
            capture_output=True, text=True, timeout=180,
        )
        assert p.returncode == 0, p.stdout + p.stderr
