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
    fora, _ = _fetch_annotations(_RepoFalso(_LINHAS), "t", "epi")
    assert [r["frame_id"] for r in fora] == ["f1", "f2"], (
        "gate de procedência: pré-anotação SEM revisão humana nunca entra"
    )


def test_somente_humano_corta_a_caixa_da_proposta_aceita() -> None:
    """Com o flag, entra SÓ o que a mão humana desenhou."""
    fora, _ = _fetch_annotations(_RepoFalso(_LINHAS), "t", "epi", somente_humano=True)
    assert [r["frame_id"] for r in fora] == ["f1"], (
        "f2 é proposta ACEITA: classe confirmada pelo humano, caixa desenhada "
        "pelo modelo — é exatamente a geometria que o v11 aprendeu errado"
    )
    assert all(r["source"] == "manual" for r in fora)


def test_o_flag_muda_o_resultado() -> None:
    """Guarda contra o flag virar no-op num refactor: os dois modos TÊM de
    divergir quando existe proposta aceita no conjunto."""
    com, _ = _fetch_annotations(_RepoFalso(_LINHAS), "t", "epi", somente_humano=True)
    sem, _ = _fetch_annotations(_RepoFalso(_LINHAS), "t", "epi", somente_humano=False)
    assert len(com) < len(sem), "somente_humano=True não pode devolver o mesmo conjunto"


class TestBracoDeVolumeControlado:
    """As duas populações do #536 são DISJUNTAS — medido no RVB.

    2.617 frames têm só proposta aceita, 2.359 têm só caixa desenhada à mão, e
    ZERO têm as duas. Não existe "mesmas imagens com menos caixas": tirar a
    geometria do modelo tira 53% dos frames INTEIROS. O primeiro desenho de
    controle (mesmos frames, todas as caixas) era um no-op nesta base — saiu
    idêntico ao braço só-humano, 3.482 caixas nos dois. O controle possível é
    igualar o VOLUME.
    """

    def test_corte_e_deterministico(self):
        from app.infrastructure.queue.tasks.versioning_v2 import _limita_frames

        frames = [{"id": f"f{i}"} for i in range(100)]
        a = _limita_frames(frames, 40, "ab-536")
        b = _limita_frames(list(reversed(frames)), 40, "ab-536")

        assert len(a) == 40
        # mesma semente e mesmo universo -> mesmo corte, mesmo que o banco
        # devolva as linhas em outra ordem
        assert {f["id"] for f in a} == {f["id"] for f in b}

    def test_semente_diferente_corta_diferente(self):
        from app.infrastructure.queue.tasks.versioning_v2 import _limita_frames

        frames = [{"id": f"f{i}"} for i in range(100)]
        a = _limita_frames(frames, 40, "x")
        b = _limita_frames(frames, 40, "y")
        assert {f["id"] for f in a} != {f["id"] for f in b}

    def test_limite_maior_que_a_base_nao_corta(self):
        from app.infrastructure.queue.tasks.versioning_v2 import _limita_frames

        frames = [{"id": f"f{i}"} for i in range(10)]
        assert len(_limita_frames(frames, 999, "x")) == 10
