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
    """O A/B do #536 fica ambíguo com dois braços de tamanhos diferentes.

    só-humano tem 2.362 frames contra 4.977 do completo. Se ele perder, pode
    ser a geometria herdada do modelo OU simplesmente metade do dado — e as
    duas leituras levam a decisões opostas. O terceiro braço usa os MESMOS
    frames do só-humano com TODAS as caixas: a única diferença é a geometria.
    """

    LINHAS = [
        # f1: tem caixa humana -> entra nos três braços
        {"frame_id": "f1", "source": "manual", "reviewed_by": None,
         "class_id": 1, "class_name": "Luvas", "x_center": 0.3, "y_center": 0.3,
         "width": 0.1, "height": 0.1},
        {"frame_id": "f1", "source": "pre_annotation", "reviewed_by": "u1",
         "class_id": 1, "class_name": "Luvas", "x_center": 0.6, "y_center": 0.6,
         "width": 0.1, "height": 0.1},
        # f2: SÓ proposta aceita -> não tem caixa humana nenhuma
        {"frame_id": "f2", "source": "pre_annotation", "reviewed_by": "u1",
         "class_id": 1, "class_name": "Luvas", "x_center": 0.4, "y_center": 0.4,
         "width": 0.1, "height": 0.1},
    ]

    def test_mesmos_frames_do_so_humano_mas_com_todas_as_caixas(self):
        from app.infrastructure.queue.tasks.versioning_v2 import _fetch_annotations

        controle, _ = _fetch_annotations(
            _RepoFalso(self.LINHAS), "t", "epi", so_frames_com_caixa_humana=True
        )
        so_humano, _ = _fetch_annotations(
            _RepoFalso(self.LINHAS), "t", "epi", somente_humano=True
        )

        # mesmo conjunto de FRAMES que o braço só-humano
        assert {a["frame_id"] for a in controle} == {a["frame_id"] for a in so_humano}
        # mas com a caixa do modelo somada: 2 caixas contra 1
        assert len(controle) == 2 and len(so_humano) == 1
        assert {a["source"] for a in controle} == {"manual", "pre_annotation"}

    def test_frame_sem_nenhuma_caixa_humana_fica_de_fora(self):
        from app.infrastructure.queue.tasks.versioning_v2 import _fetch_annotations

        controle, _ = _fetch_annotations(
            _RepoFalso(self.LINHAS), "t", "epi", so_frames_com_caixa_humana=True
        )
        assert "f2" not in {a["frame_id"] for a in controle}

    def test_sem_o_flag_o_frame_so_de_proposta_entra(self):
        """Guarda contra o flag virar no-op."""
        from app.infrastructure.queue.tasks.versioning_v2 import _fetch_annotations

        completo, _ = _fetch_annotations(_RepoFalso(self.LINHAS), "t", "epi")
        assert "f2" in {a["frame_id"] for a in completo}
        assert len(completo) == 3
