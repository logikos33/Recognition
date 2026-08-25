"""Quem decide o que é violação é o cadastro do cliente, não uma env var.

`_has_violation` lia `_VIOLATION_CLASSES`, montado de `VIOLATION_CLASSES` com
default `{no_helmet, no_vest, no_gloves}`. Medido no DEV: a variável **não está
setada** em nenhum serviço, e esses três nomes **não existem** na taxonomia do
RVB, onde as classes de ausência começam com "Sem ".

Consequência em cadeia:
  · `has_violation` era sempre falso;
  · `_save_alert` nunca era chamado por esse caminho;
  · `submit_for_verification` nunca era chamado;
  · a fila `needs_human` ficava vazia POR CONSTRUÇÃO — e a tela escrevia
    "Nenhum alerta aguardando revisão humana".

A fonte de verdade é `yolo_classes.is_violation` (ADR-0065). Conferido no banco
do DEV para o RVB: `Sem botas`, `Sem mascara`, `Sem protetor de ouvido` e
`Uso incorreto de mascara` = True; `Botas`, `mascara`, `Protetor auditivo` =
False.
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

from app.infrastructure.queue.tasks import inference as inference_mod  # noqa: E402

_CAMERA = "cam-1"
_TENANT = "63c219d8-fbef-4f3c-a7c9-058c742482e2"

# exatamente o que o banco do DEV devolve para o RVB
_VIOLACAO = frozenset({
    "sem botas", "sem mascara", "sem protetor de ouvido",
    "uso incorreto de mascara",
})
_PRESENCA = frozenset({"botas", "mascara", "protetor auditivo", "protetor auricular"})


def _limpa():
    inference_mod._polaridade_cache.clear()
    inference_mod._sem_polaridade_avisadas.clear()


def _com_polaridade(violacao=_VIOLACAO, presenca=_PRESENCA, tenant=_TENANT):
    """Patcha a resolução tenant+polaridade, deixando o resto real."""
    return patch.object(
        inference_mod, "_polaridade_da_camera",
        return_value=(violacao, presenca, tenant, "epi"),
    )


class TestPolaridadeVemDoCadastro:
    def setup_method(self):
        _limpa()

    teardown_method = setup_method

    def test_classe_de_ausencia_do_rvb_e_violacao(self):
        """O caso que o env NUNCA acertaria: 'Sem protetor de ouvido'."""
        with _com_polaridade():
            assert inference_mod._has_violation(
                _CAMERA, [{"class": "Sem protetor de ouvido", "confidence": 0.7}]
            ) is True

    def test_classe_de_presenca_nao_e_violacao(self):
        with _com_polaridade():
            assert inference_mod._has_violation(
                _CAMERA, [{"class": "Protetor auditivo", "confidence": 0.9}]
            ) is False

    def test_os_nomes_coco_do_env_nao_decidem_mais(self):
        """`no_helmet` era o único que o código reconhecia — e não existe aqui."""
        with _com_polaridade():
            assert inference_mod._has_violation(
                _CAMERA, [{"class": "no_helmet", "confidence": 0.9}]
            ) is False

    def test_comparacao_e_case_insensitive(self):
        """O cadastro guarda em lower; o modelo emite com maiúscula."""
        with _com_polaridade():
            assert inference_mod._has_violation(
                _CAMERA, [{"class": "SEM MASCARA", "confidence": 0.6}]
            ) is True

    def test_uma_violacao_no_meio_de_conformidades_basta(self):
        with _com_polaridade():
            assert inference_mod._has_violation(_CAMERA, [
                {"class": "Botas", "confidence": 0.9},
                {"class": "Protetor auditivo", "confidence": 0.8},
                {"class": "Sem mascara", "confidence": 0.5},
            ]) is True

    def test_sem_deteccao_e_falso_sem_ir_ao_banco(self):
        with patch.object(inference_mod, "_polaridade_da_camera") as p:
            assert inference_mod._has_violation(_CAMERA, []) is False
            p.assert_not_called()


class TestClasseSemPolaridadeNaoFicaMuda:
    """O modelo emite 12–13 classes; o cadastro do RVB conhece 9."""

    def setup_method(self):
        _limpa()

    teardown_method = setup_method

    def test_classe_indecidida_avisa_e_nao_alerta(self, caplog):
        with _com_polaridade(), caplog.at_level(logging.WARNING):
            # 'Sem Luvas' o modelo emite, mas não está em yolo_classes
            assert inference_mod._has_violation(
                _CAMERA, [{"class": "Sem Luvas", "confidence": 0.8}]
            ) is False
        assert "classe_sem_polaridade" in caplog.text
        assert "Sem Luvas" in caplog.text

    def test_avisa_uma_vez_por_nome(self, caplog):
        with _com_polaridade(), caplog.at_level(logging.WARNING):
            for _ in range(4):
                inference_mod._has_violation(
                    _CAMERA, [{"class": "Sem Óculos", "confidence": 0.8}]
                )
        assert caplog.text.count("classe_sem_polaridade") == 1

    def test_classe_conhecida_nao_dispara_o_aviso(self, caplog):
        with _com_polaridade(), caplog.at_level(logging.WARNING):
            inference_mod._has_violation(_CAMERA, [{"class": "Botas"}])
        assert "classe_sem_polaridade" not in caplog.text


class TestFalhaDeLeituraNaoViraNadaEViolacao:
    def setup_method(self):
        _limpa()

    teardown_method = setup_method

    def test_erro_de_banco_devolve_o_ultimo_valor_bom(self, caplog):
        pool = MagicMock()
        repo = MagicMock()
        repo.violation_class_names.return_value = list(_VIOLACAO)
        repo.presence_class_names.return_value = list(_PRESENCA)

        alvo = (
            "app.infrastructure.database.repositories."
            "alert_repository.AlertRepository"
        )
        with patch(alvo, return_value=repo):
            v1, _ = inference_mod._polaridade_do_tenant(pool, _TENANT, "epi")
        assert v1 == _VIOLACAO

        # expira o cache e faz a leitura seguinte explodir
        inference_mod._polaridade_cache[_TENANT] = (
            -1.0, *inference_mod._polaridade_cache[_TENANT][1:]
        )
        with patch(alvo, side_effect=RuntimeError("banco caiu")), \
                caplog.at_level(logging.ERROR):
            v2, _ = inference_mod._polaridade_do_tenant(pool, _TENANT, "epi")

        assert v2 == _VIOLACAO, "falha não pode apagar a polaridade conhecida"
        assert "polaridade_leitura_falhou" in caplog.text

    def test_sem_leitura_previa_devolve_vazio_e_loga(self, caplog):
        alvo = (
            "app.infrastructure.database.repositories."
            "alert_repository.AlertRepository"
        )
        with patch(alvo, side_effect=RuntimeError("banco caiu")), \
                caplog.at_level(logging.ERROR):
            v, p = inference_mod._polaridade_do_tenant(MagicMock(), "t-novo", "epi")
        assert v == frozenset() and p == frozenset()
        assert "polaridade_leitura_falhou" in caplog.text


class TestAsDuasDecisoesUsamAMesmaFonte:
    """O alerta nascia por uma regra e era verificado por outra (#132)."""

    def setup_method(self):
        _limpa()

    teardown_method = setup_method

    def test_verificacao_usa_a_polaridade_do_cadastro(self):
        enviados = []
        tarefa = MagicMock()
        tarefa.delay.side_effect = lambda **kw: enviados.append(kw)
        modulo = MagicMock(verify_alert=tarefa)

        with _com_polaridade(), \
             patch.dict(sys.modules,
                        {"app.infrastructure.queue.tasks.verification": modulo}):
            inference_mod._queue_verification_if_low_confidence(
                {"id": "a1"}, _CAMERA,
                [
                    {"class": "Sem mascara", "confidence": 0.40},
                    {"class": "no_helmet", "confidence": 0.30},
                ],
                "epi",
            )

        assert len(enviados) == 1
        assert enviados[0]["class_name"] == "Sem mascara", (
            "o nome COCO do env não pode mais entrar na fila de verificação"
        )


class TestOPromptNaoAfirmaARegraDoNo:
    """Lê a FONTE, não o módulo importado.

    `test_inference_alert_verification.py` instala um stub de
    `…tasks.verification` em `sys.modules`; importar aqui devolveria um
    MagicMock, e `"x" not in MagicMock()` não afirma nada. Passava sozinho e
    falhava na suíte — que é a assinatura dessa poluição.
    """

    def test_prompt_nao_ensina_polaridade_por_prefixo(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        fonte = (
            raiz / "app" / "infrastructure" / "queue" / "tasks" / "verification.py"
        ).read_text(encoding="utf-8")
        # sem o cabeçalho: o docstring do módulo CITA a regra antiga de
        # propósito, para explicar o defeito, e não pode disparar o guard
        corpo = fonte.split('_VERDICT_PROMPT = """\\', 1)[-1]

        assert 'começam com "no_"' not in corpo, (
            "no RVB as classes de ausência começam com 'Sem ' — a regra do "
            "prefixo não descreve a taxonomia de nenhum cliente real"
        )
        assert "JÁ FOI classificada" in corpo
