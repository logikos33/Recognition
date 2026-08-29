"""Issue #421 — o `security-scan` ficava VERDE com astro 4.16.19 vulnerável.

O job de npm audit rodava com `continue-on-error: true`: executava, imprimia as
5 vulnerabilidades da landing, e o workflow reportava success. Verde assim não é
prova de segurança — é a ausência da pergunta.

Tirar o `continue-on-error` sozinho traria de volta o motivo dele: um advisory
que cruza o limiar pinta de vermelho TODO PR, inclusive PR só de Python, e
vermelho em tudo deixa de ser sinal.

A saída é a exceção ser explícita e ter PRAZO. Estes testes fixam as três
propriedades que fazem isso funcionar.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys


_RAIZ = pathlib.Path(__file__).resolve().parents[5]
_GATE = _RAIZ / "scripts" / "ci" / "check_npm_audit.py"


def _rodar(relatorio: dict, allowlist: dict | None, tmp_path) -> tuple[int, str]:
    if allowlist is not None:
        (tmp_path / ".audit-allowlist.json").write_text(json.dumps(allowlist), encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(_GATE), str(tmp_path)],
        input=json.dumps(relatorio), capture_output=True, text=True, timeout=60,
    )
    return p.returncode, p.stdout


def _rel(**severidades) -> dict:
    return {
        "vulnerabilities": {n: {"severity": s} for n, s in severidades.items()},
        "metadata": {"vulnerabilities": {}},
    }


_VALE = {"expires": "2099-01-01", "allowed": ["astro", "sharp", "vite"]}


class TestGateDeAudit:
    def test_advisory_conhecido_no_allowlist_passa(self, tmp_path):
        cod, saida = _rodar(_rel(astro="high", sharp="high"), _VALE, tmp_path)
        assert cod == 0, saida
        assert "OK" in saida

    def test_advisory_NOVO_reprova(self, tmp_path):
        """O que o `continue-on-error` engolia."""
        cod, saida = _rodar(_rel(astro="high", lodash="critical"), _VALE, tmp_path)
        assert cod == 1
        assert "lodash" in saida and "NOVO" in saida

    def test_allowlist_VENCIDO_reprova_sozinho(self, tmp_path):
        """⚠️ É o prazo que impede a exceção de virar permanente por esquecimento."""
        vencido = {"expires": "2020-01-01", "allowed": ["astro"]}
        cod, saida = _rodar(_rel(astro="high"), vencido, tmp_path)
        assert cod == 1
        assert "VENCEU" in saida

    def test_allowlist_sem_prazo_reprova(self, tmp_path):
        cod, saida = _rodar(_rel(astro="high"), {"allowed": ["astro"]}, tmp_path)
        assert cod == 1
        assert "sem campo `expires`" in saida

    def test_moderate_nao_reprova(self, tmp_path):
        """O limiar é high — manter o mesmo de antes, para não trocar um ruído por outro."""
        cod, _ = _rodar(_rel(esbuild="moderate"), _VALE, tmp_path)
        assert cod == 0

    def test_sem_allowlist_e_sem_grave_passa(self, tmp_path):
        cod, _ = _rodar(_rel(algo="low"), None, tmp_path)
        assert cod == 0

    def test_sem_allowlist_com_grave_reprova(self, tmp_path):
        """App sem allowlist não ganha isenção por omissão."""
        cod, saida = _rodar(_rel(algo="critical"), None, tmp_path)
        assert cod == 1
        assert "algo" in saida

    def test_exceção_obsoleta_avisa_mas_nao_reprova(self, tmp_path):
        cod, saida = _rodar(_rel(astro="high"), _VALE, tmp_path)
        assert cod == 0
        assert "JÁ NÃO aparecem" in saida and "sharp" in saida

    def test_stdin_vazio_reprova(self, tmp_path):
        p = subprocess.run(
            [sys.executable, str(_GATE), str(tmp_path)],
            input="", capture_output=True, text=True, timeout=60,
        )
        assert p.returncode == 1, "audit que não produziu saída não pode passar por omissão"


class TestAllowlistRealDaLanding:
    def test_a_landing_tem_allowlist_com_prazo_futuro(self):
        import datetime as dt

        caminho = _RAIZ / "apps" / "landing" / ".audit-allowlist.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        assert dt.date.fromisoformat(dados["expires"]) > dt.date.today(), (
            "o allowlist da landing venceu — reavalie os advisories (#421) e "
            "renove a data, ou faça o upgrade do astro"
        )
        assert dados.get("motivo"), "exceção sem motivo escrito é exceção esquecida"
