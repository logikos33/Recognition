"""A checagem de proveniência precisa alertar no caso REAL de 29/08.

Naquele dia a API do DEV rodou horas um build de `railway up` enquanto a develop
tinha outro código. O `/livez` dizia `"unknown"` — o sinal existia e ninguém
lia. Estes testes garantem que o alerta dispara, e que ele NÃO dispara durante
um deploy normal (alarme que grita à toa é alarme que todo mundo ignora).
"""
import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "checa", Path(__file__).resolve().parents[1] / "scripts" / "checa_proveniencia.py"
)
checa = importlib.util.module_from_spec(_spec)
sys.modules["checa"] = checa
_spec.loader.exec_module(checa)

AGORA = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
SHA = "5d30c1c9792fb50e0b17d2a8fb2655a5f601cc70"
OUTRO = "027ecb74747c92daa06844ca6aeceb0fee920574"


def _ha(minutos: int) -> datetime:
    return AGORA - timedelta(minutes=minutos)


class TestNaoGritaAToa:
    def test_em_dia_nao_alerta(self):
        alerta, _ = checa.avaliar(SHA, SHA, _ha(120), AGORA)
        assert alerta is False

    def test_divergente_dentro_da_carencia_nao_alerta(self):
        """Commit novo + serviço no anterior = deploy em andamento, não falha."""
        alerta, motivo = checa.avaliar(OUTRO, SHA, _ha(5), AGORA)
        assert alerta is False
        assert "carência" in motivo

    def test_unknown_dentro_da_carencia_tambem_espera(self):
        alerta, _ = checa.avaliar("unknown", SHA, _ha(2), AGORA)
        assert alerta is False


class TestGritaQuandoPrecisa:
    def test_o_caso_de_29_08_unknown_por_horas(self):
        """O episódio real: `railway up` sobrescreveu o deploy por git."""
        alerta, motivo = checa.avaliar("unknown", SHA, _ha(180), AGORA)
        assert alerta is True
        assert "PROVENIÊNCIA PERDIDA" in motivo
        assert "railway up" in motivo
        assert "D-156" in motivo

    def test_atrasado_alem_da_carencia(self):
        alerta, motivo = checa.avaliar(OUTRO, SHA, _ha(45), AGORA)
        assert alerta is True
        assert "ATRASADO" in motivo
        assert OUTRO[:8] in motivo and SHA[:8] in motivo

    def test_servico_mudo_alerta_na_hora(self):
        """Sem resposta não há carência: ou está fora do ar, ou não responde."""
        alerta, motivo = checa.avaliar(None, SHA, _ha(1), AGORA)
        assert alerta is True
        assert "não respondeu" in motivo

    def test_respondeu_sem_o_campo_e_outro_diagnostico(self):
        """Achado da calibração: apontar a checagem para `/health` fazia o
        script dizer "não respondeu" — e o serviço TINHA respondido. As duas
        situações pedem ação diferente: uma é ressuscitar o serviço, a outra é
        conferir a URL. Um alerta que erra o diagnóstico manda a pessoa para o
        lugar errado."""
        alerta, motivo = checa.avaliar(checa.SEM_CAMPO, SHA, _ha(1), AGORA)
        assert alerta is True
        assert "SEM o campo" in motivo
        assert "não respondeu" not in motivo

    def test_sem_campo_nao_espera_carencia(self):
        # Não é deploy em andamento: o serviço está de pé e não declara nada.
        assert checa.avaliar(checa.SEM_CAMPO, SHA, _ha(1), AGORA)[0] is True


class TestBordaDaCarencia:
    def test_um_minuto_antes_espera_um_depois_alerta(self):
        assert checa.avaliar("unknown", SHA, _ha(checa.CARENCIA_MINUTOS - 1), AGORA)[0] is False
        assert checa.avaliar("unknown", SHA, _ha(checa.CARENCIA_MINUTOS + 1), AGORA)[0] is True


# ---------------------------------------------------------------------------
# 05/09 — o vigia precisa saber a diferença entre DECLARADO e PROVADO
#
# Até aqui esta checagem comparava `/livez.commit` com o HEAD da develop e dava
# ✅ quando batiam. Só que `commit` sai de env var que o CI grava ANTES de
# subir: se o upload falha, sobe outra árvore, ou alguém dá um `railway up` de
# fora do CI (que não toca a variável), o serviço AFIRMA um SHA que não está
# rodando — e o vigia confirmava.
#
# Um alarme que não distingue "me disseram" de "eu conferi" mente com voz de
# autoridade. Estes testes fixam a distinção.
# ---------------------------------------------------------------------------

DIGEST_OK = "42e6f43873d48789"
DIGEST_OUTRO = "0000ffff0000ffff"


class TestDeclaradoNaoEProvado:
    def test_o_defeito_de_05_09_sha_certo_codigo_errado(self):
        """FALHA ANTES: a versão anterior devolvia ✅ neste exato cenário.

        O serviço declara o SHA da develop (a env var foi gravada) mas o código
        que ele tem em disco é outro. Isto é o pior caso possível: parece
        saudável e não é.
        """
        alerta, motivo = checa.avaliar(
            SHA, SHA, _ha(120), AGORA,
            digest_servido=DIGEST_OUTRO, digest_esperado=DIGEST_OK,
        )
        assert alerta is True
        assert "DECLARAÇÃO FALSA" in motivo
        assert "env var" in motivo

    def test_sem_digest_o_veredito_diz_que_nao_provou(self):
        """✅ continua ✅ — mas com o rótulo certo. O sinal honesto de antes era
        `unknown`; trocar por um ✅ mudo foi o que apagou a informação."""
        alerta, motivo = checa.avaliar(SHA, SHA, _ha(120), AGORA)
        assert alerta is False
        assert "NÃO PROVADO" in motivo

    def test_digest_batendo_e_prova_de_verdade(self):
        alerta, motivo = checa.avaliar(
            SHA, SHA, _ha(120), AGORA,
            digest_servido=DIGEST_OK, digest_esperado=DIGEST_OK,
        )
        assert alerta is False
        assert "PROVADO" in motivo
        assert "NÃO PROVADO" not in motivo

    def test_provado_diz_o_que_provou_e_o_que_nao(self):
        """PROVADO sem escopo seria a mesma mentira, um degrau menor.

        O digest cobre `services/api/app/**/*.py` e mais nada. Um veredito que
        afirma "o código servido" inteiro é largo demais para a evidência que o
        sustenta — e quem lê o alarme às 3h age em cima da linha, não do
        runbook. Se alguém encolher a mensagem, este teste reprova.
        """
        _, motivo = checa.avaliar(
            SHA, SHA, _ha(120), AGORA,
            digest_servido=DIGEST_OK, digest_esperado=DIGEST_OK,
        )
        assert checa.PACOTE_SERVIDO in motivo, motivo
        assert "FORA do digest" in motivo, motivo
        assert "railway_start.py" in motivo and "frontend" in motivo, motivo

    def test_digest_batendo_vale_mais_que_a_declaracao_ausente(self):
        """`unknown` + digest batendo = deploy por upload com código CERTO.

        É o caso do CI de hoje (`railway up` não carrega SHA). Antes o vigia
        ficaria vermelho para sempre nesse caminho — alarme que grita à toa é
        alarme que ninguém lê. O digest resolve sem afrouxar nada: a prova não
        veio da declaração, veio do código.
        """
        alerta, motivo = checa.avaliar(
            "unknown", SHA, _ha(180), AGORA,
            digest_servido=DIGEST_OK, digest_esperado=DIGEST_OK,
        )
        assert alerta is False
        assert "PROVADO" in motivo

    def test_codigo_divergente_e_sha_divergente_alerta_com_prova(self):
        alerta, motivo = checa.avaliar(
            OUTRO, SHA, _ha(45), AGORA,
            digest_servido=DIGEST_OUTRO, digest_esperado=DIGEST_OK,
        )
        assert alerta is True
        assert "PROVADO pelo digest" in motivo

    def test_codigo_divergente_dentro_da_carencia_ainda_espera(self):
        alerta, motivo = checa.avaliar(
            OUTRO, SHA, _ha(5), AGORA,
            digest_servido=DIGEST_OUTRO, digest_esperado=DIGEST_OK,
        )
        assert alerta is False
        assert "carência" in motivo

    def test_digest_so_de_um_lado_nao_vira_prova(self):
        """Ausência de prova NUNCA vira prova — nem quando falta do lado do
        serviço, nem quando o `git ls-tree` falhou aqui."""
        for servido, esperado_dig in ((DIGEST_OK, None), (None, DIGEST_OK)):
            alerta, motivo = checa.avaliar(
                SHA, SHA, _ha(120), AGORA,
                digest_servido=servido, digest_esperado=esperado_dig,
            )
            assert alerta is False
            assert "NÃO PROVADO" in motivo

    def test_carencia_configuravel_para_conferir_logo_apos_o_deploy(self):
        """`--carencia-min 0`: depois de um deploy a pergunta é "subiu mesmo?",
        e não há o que esperar."""
        assert checa.avaliar(
            SHA, SHA, _ha(1), AGORA,
            digest_servido=DIGEST_OUTRO, digest_esperado=DIGEST_OK,
        )[0] is False
        assert checa.avaliar(
            SHA, SHA, _ha(1), AGORA,
            digest_servido=DIGEST_OUTRO, digest_esperado=DIGEST_OK,
            carencia_min=0,
        )[0] is True


class TestDiagnosticoDaFalhaDeRede:
    def test_o_motivo_bruto_chega_ao_veredito(self):
        """TLS quebrado, DNS e timeout pedem ações diferentes. "não respondeu"
        sozinho manda reiniciar um serviço que pode estar saudável — foi o que
        aconteceu ao rodar isto num macOS sem certificados raiz."""
        alerta, motivo = checa.avaliar(
            None, SHA, _ha(1), AGORA,
            erro_rede="URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED]>",
        )
        assert alerta is True
        assert "CERTIFICATE_VERIFY_FAILED" in motivo

    def test_sem_motivo_continua_legivel(self):
        assert "não respondeu" in checa.avaliar(None, SHA, _ha(1), AGORA)[1]
