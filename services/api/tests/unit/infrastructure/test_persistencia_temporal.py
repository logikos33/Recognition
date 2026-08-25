"""ADR-0067: veredito num frame só não é violação — tem de se SUSTENTAR.

`_save_alert` rodava a cada frame com violação, sem cooldown nenhum. A tabela
`alert_rules` tinha os campos (`min_occurrences`, `time_window_seconds`) desde
a migration 006 e **nenhum consumidor** — write-only + read-to-display.

Estado do cadastro em 25/08: 3.270 linhas, e todas as semeadas são
`no_helmet`/`no_vest` — a taxonomia de demonstração da era COCO, inclusive as
do RVB. Nenhuma casa com classe real, então hoje o mapa sai VAZIO e o
comportamento fica idêntico ao anterior. Isso é deliberado: o mecanismo entra
pronto e desligado; ligar por classe é cadastrar a regra com o nome que o
modelo realmente emite.

⚠️ Direção da falha, e por que ela é o OPOSTO da do `/health`:

  `/health` falha FECHADO — na dúvida, "não sei" nunca vira "está tudo bem".
  Aqui falha ABERTO — Redis indisponível deixa o alerta passar.

Não é incoerência: as perguntas são diferentes. Lá é "está saudável?", e
otimismo esconde problema. Aqui é "houve violação?", e pessimismo APAGA
evento — num produto de segurança, perder violação é o erro caro.
"""
from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_INFERENCE_KEY = "app.infrastructure.queue.tasks.inference"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_INFERENCE_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import inference as mod  # noqa: E402

_CAMERA = "cam-1"
_TENANT = "63c219d8-fbef-4f3c-a7c9-058c742482e2"
_DET = [{"class": "Sem mascara", "confidence": 0.7}]


def _redis_contando(*contagens):
    """Redis falso cujo `zcard` devolve as contagens na ordem dada."""
    r = MagicMock()
    pipe = MagicMock()
    r.pipeline.return_value = pipe
    pipe.execute.side_effect = [[1, 0, n, True] for n in contagens]
    return r


def _com_regras(regras):
    mod._regras_cache.clear()
    return (
        patch.object(mod, "_regras_de_persistencia", return_value=regras),
        patch.object(mod, "_camera_tenant_module", return_value=(_TENANT, "epi")),
        patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=MagicMock(),
        ),
    )


class TestSemRegraOComportamentoNaoMuda:
    def test_mapa_vazio_deixa_passar_na_hora(self):
        a, b, c = _com_regras({})
        with a, b, c:
            assert mod._persistencia_satisfeita(_CAMERA, _DET, _redis_contando(1)) is True

    def test_classe_sem_regra_alerta_na_hora(self):
        """A regra é por CLASSE, não por frame."""
        a, b, c = _com_regras({"sem luvas": (3, 30)})
        with a, b, c:
            assert mod._persistencia_satisfeita(_CAMERA, _DET, _redis_contando(1)) is True

    def test_sem_deteccao_nao_consulta_nada(self):
        r = MagicMock()
        assert mod._persistencia_satisfeita(_CAMERA, [], r) is True
        r.pipeline.assert_not_called()


class TestComRegraOAlertaEsperaSeSustentar:
    def test_primeira_ocorrencia_ainda_nao_alerta(self):
        a, b, c = _com_regras({"sem mascara": (3, 30)})
        with a, b, c:
            assert mod._persistencia_satisfeita(_CAMERA, _DET, _redis_contando(1)) is False

    def test_segunda_tambem_nao(self):
        a, b, c = _com_regras({"sem mascara": (3, 30)})
        with a, b, c:
            assert mod._persistencia_satisfeita(_CAMERA, _DET, _redis_contando(2)) is False

    def test_terceira_alerta(self, caplog):
        a, b, c = _com_regras({"sem mascara": (3, 30)})
        with a, b, c, caplog.at_level(logging.INFO):
            assert mod._persistencia_satisfeita(_CAMERA, _DET, _redis_contando(3)) is True
        assert "persistencia_satisfeita" in caplog.text

    def test_a_janela_e_deslizante(self):
        """`zremrangebyscore` corta o que saiu da janela ANTES de contar —
        senão 3 ocorrências espalhadas por uma hora contariam como surto."""
        a, b, c = _com_regras({"sem mascara": (3, 30)})
        r = _redis_contando(1)
        with a, b, c:
            mod._persistencia_satisfeita(_CAMERA, _DET, r)
        chamadas = [str(x) for x in r.pipeline.return_value.method_calls]
        assert any("zremrangebyscore" in x for x in chamadas)
        assert any("zadd" in x for x in chamadas)
        assert any("expire" in x for x in chamadas)

    def test_contador_e_por_camera_E_por_classe(self):
        a, b, c = _com_regras({"sem mascara": (3, 30)})
        r = _redis_contando(1)
        with a, b, c:
            mod._persistencia_satisfeita(_CAMERA, _DET, r)
        chave = str(r.pipeline.return_value.method_calls[0])
        assert _CAMERA in chave and "sem mascara" in chave


class TestFalhaDeixaPassar:
    def test_redis_fora_do_ar_nao_apaga_alerta(self, caplog):
        a, b, c = _com_regras({"sem mascara": (3, 30)})
        r = MagicMock()
        r.pipeline.side_effect = RuntimeError("redis caiu")
        with a, b, c, caplog.at_level(logging.WARNING):
            assert mod._persistencia_satisfeita(_CAMERA, _DET, r) is True
        assert "persistencia_redis_falhou" in caplog.text

    def test_sem_pool_deixa_passar(self):
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=None,
        ):
            assert mod._persistencia_satisfeita(_CAMERA, _DET, MagicMock()) is True

    def test_sem_tenant_deixa_passar(self):
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=MagicMock(),
        ), patch.object(mod, "_camera_tenant_module", return_value=(None, None)):
            assert mod._persistencia_satisfeita(_CAMERA, _DET, MagicMock()) is True


class TestLeituraDasRegras:
    def _repo_devolvendo(self, linhas):
        repo = MagicMock()
        repo._execute.return_value = linhas
        return patch(
            "app.infrastructure.database.repositories.base.BaseRepository",
            return_value=repo,
        ), repo

    def test_so_regra_com_minimo_maior_que_um(self):
        """`min_occurrences = 1` é o comportamento de sempre e não precisa de
        contador — o SQL já filtra, e o teste fixa isso."""
        p, repo = self._repo_devolvendo([])
        mod._regras_cache.clear()
        with p:
            mod._regras_de_persistencia(MagicMock(), _TENANT)
        sql = repo._execute.call_args[0][0]
        assert "min_occurrences > 1" in sql
        assert "enabled IS TRUE" in sql
        assert "create_alert IS TRUE" in sql

    def test_janela_ausente_usa_o_padrao(self):
        p, _repo = self._repo_devolvendo(
            [{"classe": "sem mascara", "min_occurrences": 3, "time_window_seconds": None}]
        )
        mod._regras_cache.clear()
        with p:
            regras = mod._regras_de_persistencia(MagicMock(), _TENANT)
        assert regras["sem mascara"] == (3, mod._JANELA_PADRAO_S)

    def test_erro_de_banco_mantem_o_ultimo_valor_bom(self, caplog):
        p, repo = self._repo_devolvendo(
            [{"classe": "sem mascara", "min_occurrences": 2, "time_window_seconds": 10}]
        )
        mod._regras_cache.clear()
        with p:
            bom = mod._regras_de_persistencia(MagicMock(), _TENANT)
        assert bom["sem mascara"] == (2, 10)

        mod._regras_cache[_TENANT] = (-1.0, mod._regras_cache[_TENANT][1])
        with patch(
            "app.infrastructure.database.repositories.base.BaseRepository",
            side_effect=RuntimeError("banco caiu"),
        ), caplog.at_level(logging.ERROR):
            depois = mod._regras_de_persistencia(MagicMock(), _TENANT)
        assert depois == bom, "falha não pode apagar a regra conhecida"
        assert "regras_persistencia_falharam" in caplog.text
