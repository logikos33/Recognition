"""#421 — o `security-scan` ficava VERDE com astro 4.16.19 vulnerável.

O job de npm audit rodava com `continue-on-error: true`: executava, imprimia as
5 vulnerabilidades da landing, e o workflow reportava success. Verde assim não é
prova de segurança — é a ausência da pergunta.

O gate que substituiu isso vivia num heredoc dentro do `security-scan.yml`, ou
seja: 55 linhas de política de segurança que **nenhum teste podia executar**.
Estes testes fixam as propriedades que fazem o gate valer alguma coisa, agora
que ele é um arquivo importável.

Prova de que o teste morde: trocar `hoje > prazo` por `hoje >= prazo`,
`NIVEL[...] > NIVEL[teto]` por `>=`, ou remover o `return 1` do stdin inválido
faz cada um destes reprovar.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[5]
_GATE = _RAIZ / "scripts" / "ci" / "check_npm_audit.py"

sys.path.insert(0, str(_GATE.parent))
from check_npm_audit import ALLOWLIST, avaliar  # noqa: E402


def _rel(**severidades) -> dict:
    return {"vulnerabilities": {n: {"severity": s} for n, s in severidades.items()}}


HOJE = "2026-09-05"


class TestGateDeAudit:
    def test_advisory_conhecido_dentro_do_prazo_passa(self):
        cod, saida = avaliar("landing", _rel(astro="high", sharp="high"), HOJE)
        assert cod == 0, saida
        assert "TOLERADO" in saida and "#421" in saida

    def test_advisory_NOVO_reprova(self):
        """Exatamente o que o `continue-on-error` engolia."""
        cod, saida = avaliar("landing", _rel(astro="high", lodash="critical"), HOJE)
        assert cod == 1
        assert "lodash" in saida and "NAO PREVISTA" in saida

    def test_advisory_NOVO_high_reprova(self):
        """⚠️ O limiar que de fato dispara aqui é `high`, ⛔ não `critical`.

        Toda entrada da allowlist real é high (browserslist, astro, sharp,
        vite) — zero critical. Um gate que só reprovasse critical passaria
        despercebido por todos os outros testes desta classe, que usam
        critical no caminho do advisory novo. Mutação que mata: reprovar só
        quando `v["severity"] == "critical"` no ramo `nome not in permitido`.
        """
        cod, saida = avaliar("frontend", _rel(browserslist="high", lodash="high"), HOJE)
        assert cod == 1, saida
        assert "lodash" in saida and "NAO PREVISTA" in saida

    def test_prazo_VENCIDO_reprova_sozinho(self):
        """⚠️ É o prazo que impede a exceção de virar permanente por esquecimento."""
        cod, saida = avaliar("landing", _rel(astro="high"), "2027-01-01")
        assert cod == 1
        assert "PRAZO VENCIDO" in saida

    def test_advisory_que_PIOROU_acima_do_teto_reprova(self):
        """A severidade da allowlist é TETO, não rótulo: high triado não cobre critical."""
        cod, saida = avaliar("landing", _rel(astro="critical"), HOJE)
        assert cod == 1
        assert "PIOROU" in saida and "astro" in saida

    def test_moderate_nao_reprova(self):
        """O limiar é high — não trocar um ruído por outro."""
        cod, _ = avaliar("landing", _rel(esbuild="moderate", algo="low"), HOJE)
        assert cod == 0

    def test_app_sem_allowlist_nao_ganha_isencao_por_omissao(self):
        cod, saida = avaliar("app-que-nao-existe", _rel(algo="critical"), HOJE)
        assert cod == 1
        assert "algo" in saida

    def test_excecao_obsoleta_avisa_mas_nao_reprova(self):
        cod, saida = avaliar("landing", _rel(astro="high"), HOJE)
        assert cod == 0
        assert "pode remover" in saida and "sharp" in saida

    def test_relatorio_limpo_passa(self):
        cod, saida = avaliar("frontend", _rel(), HOJE)
        assert cod == 0 and "OK" in saida


class TestFronteiraDoProcesso:
    """O CI chama por linha de comando, não pela função — teste cruza essa fronteira."""

    def _rodar(self, app: str, entrada: str) -> tuple[int, str]:
        p = subprocess.run(
            [sys.executable, str(_GATE), app],
            input=entrada, capture_output=True, text=True, timeout=60,
        )
        return p.returncode, p.stdout + p.stderr

    def test_stdin_vazio_reprova(self):
        """`npm audit` que morreu (rede, 400, tree inválida) ⛔ não pode passar por omissão."""
        cod, saida = self._rodar("landing", "")
        assert cod == 1, saida
        assert "nao produziu relatorio utilizavel" in saida

    def test_json_sem_a_chave_vulnerabilities_reprova(self):
        cod, saida = self._rodar("landing", json.dumps({"metadata": {}}))
        assert cod == 1, saida

    def test_saida_zero_com_relatorio_valido(self):
        cod, saida = self._rodar("frontend", json.dumps(_rel(algo="low")))
        assert cod == 0, saida


class TestAllowlistReal:
    """A allowlist do repositório é dado de produção do gate — vale conferir."""

    @pytest.mark.parametrize("app", sorted(ALLOWLIST))
    def test_toda_entrada_tem_issue_prazo_e_teto_valido(self, app):
        import datetime as dt

        for pacote, (issue, prazo, teto) in ALLOWLIST[app].items():
            assert issue.startswith("#"), f"{app}/{pacote}: exceção sem issue é exceção órfã"
            dt.date.fromisoformat(prazo)
            assert teto in ("high", "critical"), f"{app}/{pacote}: teto inválido {teto!r}"

    def test_nenhum_prazo_ja_venceu(self):
        """Se este teste ficar vermelho, o prazo chegou: reavalie ou conserte — ⛔ não estenda no escuro."""
        import datetime as dt

        hoje = dt.date.today()
        vencidos = [
            f"{app}/{pac} ({issue}, venceu {prazo})"
            for app, pacotes in ALLOWLIST.items()
            for pac, (issue, prazo, _) in pacotes.items()
            if dt.date.fromisoformat(prazo) < hoje
        ]
        assert not vencidos, "allowlist vencida: " + ", ".join(vencidos)
