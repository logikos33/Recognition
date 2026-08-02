"""
Tests: validação de faixa das envs numéricas críticas no boot (mutirão 2.6).

Família de bugs: config numérica fora de faixa → zero frame, zero erro. Regra:
fora do domínio → falha ALTA no boot (SystemExit(78)), nunca degradação
silenciosa. Testes falha-antes/passa-depois: sem este módulo, NENHUM destes
casos de "fora de faixa" impedia o boot — o processo subia normalmente e a
coleta quebrava depois, sem log nenhum.
"""
import logging

import pytest

from app.core.config_validation import validate_critical_config


def test_all_defaults_do_not_raise(monkeypatch):
    """Sem nenhuma env setada, os defaults (idênticos aos de cada ponto de
    leitura real) são válidos — boot não deve ser afetado."""
    for name in (
        "HLS_SEGMENT_TIME", "HLS_LIST_SIZE", "HLS_INACTIVITY_TIMEOUT",
        "HLS_STALL_TIMEOUT", "HLS_PLAYBACK_TOKEN_TTL",
        "EDGE_OFFLINE_THRESHOLD_SECONDS", "LIVENESS_GAP_THRESHOLD_MINUTES",
        "YOLO_INFERENCE_EVERY_N_FRAMES", "QUALITY_INFERENCE_FPS",
        "DETECTION_CONFIDENCE_THRESHOLD", "VERIFICATION_THRESHOLD",
        "DRIFT_SCORE_ALERT_THRESHOLD", "AUTO_CAPTURE_DEDUP_TTL_SECONDS",
        "DB_POOL_MIN", "DB_POOL_MAX",
    ):
        monkeypatch.delenv(name, raising=False)

    validate_critical_config(testing=False)  # não deve levantar


def test_testing_flag_skips_validation_even_with_garbage_env(monkeypatch):
    """config.TESTING=True pula a validação inteira (usado por create_app('testing'))."""
    monkeypatch.setenv("HLS_LIST_SIZE", "0")
    monkeypatch.setenv("DETECTION_CONFIDENCE_THRESHOLD", "5")

    validate_critical_config(testing=True)  # não deve levantar


def test_single_out_of_range_env_kills_boot(monkeypatch, caplog):
    """HLS_LIST_SIZE=0 é exatamente o bug que derruba o playlist HLS em
    silêncio — deve matar o boot com SystemExit(78)."""
    monkeypatch.setenv("HLS_LIST_SIZE", "0")

    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit) as exc_info:
            validate_critical_config(testing=False)

    assert exc_info.value.code == 78
    assert "HLS_LIST_SIZE" in caplog.text


def test_multiple_violations_aggregated_in_one_message(monkeypatch, caplog):
    """Falha-antes/passa-depois do ponto central do item 1: três envs erradas
    de uma vez devem aparecer TODAS na mesma mensagem/exceção — não uma por
    deploy/restart (foi assim que o incidente se repetiu 3x)."""
    monkeypatch.setenv("HLS_LIST_SIZE", "0")
    monkeypatch.setenv("DETECTION_CONFIDENCE_THRESHOLD", "5")
    monkeypatch.setenv("HLS_PLAYBACK_TOKEN_TTL", "-1")

    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit) as exc_info:
            validate_critical_config(testing=False)

    assert exc_info.value.code == 78
    assert "HLS_LIST_SIZE" in caplog.text
    assert "DETECTION_CONFIDENCE_THRESHOLD" in caplog.text
    assert "HLS_PLAYBACK_TOKEN_TTL" in caplog.text


def test_non_numeric_value_is_reported_not_silently_cast(monkeypatch, caplog):
    """Valor não numérico (ex.: env colada errada no Railway) deve ser
    reportado — nunca silenciosamente ignorado."""
    monkeypatch.setenv("HLS_SEGMENT_TIME", "abc")

    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit) as exc_info:
            validate_critical_config(testing=False)

    assert exc_info.value.code == 78
    assert "HLS_SEGMENT_TIME" in caplog.text


def test_db_pool_min_greater_than_max_raises(monkeypatch, caplog):
    """DB_POOL_MIN > DB_POOL_MAX é fisicamente impossível (pool nasce vazio
    de conexões úteis) — validação cruzada via model_validator."""
    monkeypatch.setenv("DB_POOL_MIN", "20")
    monkeypatch.setenv("DB_POOL_MAX", "5")

    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit) as exc_info:
            validate_critical_config(testing=False)

    assert exc_info.value.code == 78
    assert "DB_POOL_MIN" in caplog.text


def test_boundary_values_are_accepted(monkeypatch):
    """Limites inclusivos (ge/le) não devem ser rejeitados."""
    monkeypatch.setenv("HLS_LIST_SIZE", "20")
    monkeypatch.setenv("HLS_SEGMENT_TIME", "1")
    monkeypatch.setenv("DETECTION_CONFIDENCE_THRESHOLD", "0.0")
    monkeypatch.setenv("VERIFICATION_THRESHOLD", "1.0")

    validate_critical_config(testing=False)  # não deve levantar


def test_just_past_boundary_is_rejected(monkeypatch, caplog):
    """Um passo além do limite deve falhar (ge/le são inclusivos, não folgados)."""
    monkeypatch.setenv("HLS_LIST_SIZE", "21")

    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit) as exc_info:
            validate_critical_config(testing=False)

    assert exc_info.value.code == 78
    assert "HLS_LIST_SIZE" in caplog.text
