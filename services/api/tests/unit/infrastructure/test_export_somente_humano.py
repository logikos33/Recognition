"""Export só-humano (#536) — a caixa aceita não entra no treino de localização.

Por que este teste existe: aceitar uma proposta com uma tecla confirma a
CLASSE, não a CAIXA — a geometria que entra no dataset é a que o MODELO
desenhou. Medido no A/B de 24/08: o v11, com 38,4% das caixas vindas de
proposta aceita, PERDEU em IoU (0,67 contra 0,84) para o v10-base, que tinha
metade do dado. `somente_humano=True` corta essa realimentação.
"""
from app.infrastructure.queue.tasks.versioning_v2 import _fetch_annotations


class _RepoFalso:
    """Devolve as 3 origens que existem na coluna `source`."""

    def __init__(self, linhas):
        self._linhas = linhas

    def _execute(self, *_args, **_kwargs):
        return self._linhas


_LINHAS = [
    {"frame_id": "f1", "class_name": "mascara", "source": "manual", "reviewed_by": None},
    {"frame_id": "f2", "class_name": "Botas", "source": "pre_annotation",
     "reviewed_by": "humano-que-aceitou"},
    {"frame_id": "f3", "class_name": "Luvas", "source": "pre_annotation", "reviewed_by": None},
]


def test_padrao_aceita_proposta_revisada() -> None:
    """Sem o flag, o comportamento histórico (D-39) segue: manual + aceita."""
    fora = _fetch_annotations(_RepoFalso(_LINHAS), "t", "epi")
    assert [r["frame_id"] for r in fora] == ["f1", "f2"], (
        "gate de procedência: pré-anotação SEM revisão humana nunca entra"
    )


def test_somente_humano_corta_a_caixa_da_proposta_aceita() -> None:
    """Com o flag, entra SÓ o que a mão humana desenhou."""
    fora = _fetch_annotations(_RepoFalso(_LINHAS), "t", "epi", somente_humano=True)
    assert [r["frame_id"] for r in fora] == ["f1"], (
        "f2 é proposta ACEITA: classe confirmada pelo humano, caixa desenhada "
        "pelo modelo — é exatamente a geometria que o v11 aprendeu errado"
    )
    assert all(r["source"] == "manual" for r in fora)


def test_o_flag_muda_o_resultado() -> None:
    """Guarda contra o flag virar no-op num refactor: os dois modos TÊM de
    divergir quando existe proposta aceita no conjunto."""
    com = _fetch_annotations(_RepoFalso(_LINHAS), "t", "epi", somente_humano=True)
    sem = _fetch_annotations(_RepoFalso(_LINHAS), "t", "epi", somente_humano=False)
    assert len(com) < len(sem), "somente_humano=True não pode devolver o mesmo conjunto"
