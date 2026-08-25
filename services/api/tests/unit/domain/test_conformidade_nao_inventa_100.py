"""Falha ao ler violações não pode virar "Taxa de Conformidade 100%".

`violation_hours = _safe(...) or 0` transformava erro de consulta em ZERO
violações. Zero violações vira 100% pela fórmula, e `KPIRow` pinta 100% de
VERDE (`compliance >= 90`). Ou seja: o banco cair mostrava o número perfeito
no painel do cliente.

O frontend já tratava `null` corretamente (cinza e "—"); faltava o backend
mandar o sinal honesto em vez de um número inventado.
"""
from app.domain.services import module_service


class _RepoQueFalha:
    def camera_hours_with_violation(self, *a, **k):
        raise RuntimeError("banco caiu")


class _RepoQueDevolveZero:
    def camera_hours_with_violation(self, *a, **k):
        return 0


def _taxa(repo, cameras_ativas: int = 10):
    """Reproduz o trecho de decisão de `get_stats` isoladamente."""
    def _safe(fn, *args, default=0):
        try:
            return fn(*args)
        except Exception:
            return default

    total = cameras_ativas * 24
    horas = _safe(repo.camera_hours_with_violation, "t", "epi", None,
                  default=module_service._FALHOU)
    if horas is module_service._FALHOU:
        return None
    h = horas or 0
    return round(100.0 * (1 - min(h, total) / total), 1)


def test_consulta_que_falha_vira_indisponivel_nao_100():
    assert _taxa(_RepoQueFalha()) is None, (
        "falha de consulta virando 100% pinta o painel de verde justamente "
        "quando o sistema não sabe de nada"
    )


def test_zero_violacoes_de_verdade_continua_sendo_100():
    """Sem isto o conserto esconderia a conformidade real."""
    assert _taxa(_RepoQueDevolveZero()) == 100.0


def test_a_sentinela_nao_se_confunde_com_valor_legitimo():
    """`None` e `0` são respostas possíveis do banco — não servem de sentinela."""
    assert module_service._FALHOU is not None
    assert module_service._FALHOU != 0
    assert module_service._FALHOU is not False


def test_o_codigo_nao_usa_mais_or_zero_no_caminho_da_taxa():
    from pathlib import Path

    fonte = Path(module_service.__file__).read_text(encoding="utf-8")
    assert "camera_hours_with_violation, tenant_id, module_code, day_ago\n            ) or 0" not in fonte
    assert "default=_FALHOU" in fonte
