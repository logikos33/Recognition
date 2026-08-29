"""Campos que afirmavam mais do que sabiam, em `get_stations_live`.

`online` devolvia `True` FIXO e `shift_stats` devolvia `{"ok":0,"nok":0}` FIXO.
Os dois pareciam dado e não eram: a tela mostrava toda bancada no ar, inclusive
as desligadas, e todo turno zerado, inclusive os cheios de trabalho.

Instrumento quebrado é pior que instrumento ausente — quem lê acredita.
"""
from datetime import UTC, datetime

from app.api.v1.quality.gate_repository import _somar_turno, turno_corrente


class TestTurnoCorrente:
    """A regra do turno é a MESMA de `routes._current_shift`. Duplicada em dois
    lugares, ela divergiria na virada e as contagens ficariam de turnos
    diferentes sem ninguém notar."""

    def test_faixas(self):
        h = lambda x: datetime(2026, 8, 29, x, tzinfo=UTC)  # noqa: E731
        assert turno_corrente(h(6)) == "morning"
        assert turno_corrente(h(13)) == "morning"
        assert turno_corrente(h(14)) == "afternoon"
        assert turno_corrente(h(21)) == "afternoon"
        assert turno_corrente(h(22)) == "night"
        assert turno_corrente(h(5)) == "night"

    def test_bate_com_a_regra_de_routes(self):
        from app.api.v1.quality.routes import _current_shift

        agora = datetime.now(UTC)
        assert turno_corrente(agora) == _current_shift()


class TestSomarTurno:
    POR_CAMERA = {
        "cam-1": {"ok": 7, "nok": 2},
        "cam-2": {"ok": 3, "nok": 1},
        "cam-outra": {"ok": 99, "nok": 99},
    }

    def test_soma_as_cameras_da_bancada_e_so_elas(self):
        assert _somar_turno(["cam-1", "cam-2"], self.POR_CAMERA) == {"ok": 10, "nok": 3}

    def test_bancada_sem_camera_conta_zero_de_verdade(self):
        # Zero porque ela não inspecionou nada — diferente do zero FIXO de
        # antes, que valia igual para bancada cheia de trabalho.
        assert _somar_turno([], self.POR_CAMERA) == {"ok": 0, "nok": 0}

    def test_camera_sem_inspecao_no_turno_nao_quebra(self):
        assert _somar_turno(["cam-1", "cam-sem-nada"], self.POR_CAMERA) == {"ok": 7, "nok": 2}

    def test_camera_ids_malformado_nao_derruba_o_painel(self):
        # `camera_ids` é JSONB: pode vir None, dict, string. Nenhum desses pode
        # estourar um endpoint que o painel recarrega sozinho.
        for ruim in (None, {}, "cam-1", 42):
            assert _somar_turno(ruim, self.POR_CAMERA) == {"ok": 0, "nok": 0}

    def test_id_numerico_casa_por_string(self):
        assert _somar_turno([1], {"1": {"ok": 4, "nok": 0}}) == {"ok": 4, "nok": 0}


class TestOnlineNaoMente:
    def test_o_campo_nao_e_mais_hardcoded_true(self):
        """Guarda de regressão sobre o CÓDIGO: não há fonte de liveness em
        `quality_stations` (só `is_active`, que é cadastro), então `online` tem
        de sair como None. Se alguém devolver True fixo de novo, isto reprova."""
        from pathlib import Path

        fonte = Path(
            __file__
        ).resolve().parents[3] / "app" / "api" / "v1" / "quality" / "gate_repository.py"
        texto = fonte.read_text(encoding="utf-8")
        assert '"online": True' not in texto, (
            "online voltou a ser True fixo — não há coluna de heartbeat que sustente isso"
        )
        assert '"online": None' in texto
