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


class TestBordaDaCarencia:
    def test_um_minuto_antes_espera_um_depois_alerta(self):
        assert checa.avaliar("unknown", SHA, _ha(checa.CARENCIA_MINUTOS - 1), AGORA)[0] is False
        assert checa.avaliar("unknown", SHA, _ha(checa.CARENCIA_MINUTOS + 1), AGORA)[0] is True
