"""Guardas do dataset unificado multi-escala.

Três coisas podem produzir aqui um dataset que PARECE certo e ensina errado, e
cada uma tem teste com MUTAÇÃO (a mutação prova que o teste reprova de verdade;
sem ela um teste pode passar para sempre sem provar nada):

1. **Reprojeção do recorte sintético.** Errar o offset da janela move toda caixa
   do dataset alguns pixels — o modelo aprende localização errada e nada acusa.
2. **Vazamento do gabarito.** Os 246 quadros julgados pelo dono
   (`dataset_role='holdout'`, migration 133) no treino fazem toda medição futura
   mentir para cima. A trava vive em `versioning_v2`; aqui se prova que o caminho
   novo passa por ela.
3. **Mapeamento da taxonomia pública.** `no glove` é AUSÊNCIA. Mapeá-la para
   `Luvas` ensinaria o CONTRÁRIO do que a imagem mostra, com o dataset inteiro
   parecendo saudável.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[4]
_OPS = _RAIZ / "scripts" / "ops"


def _carrega(nome: str):
    spec = importlib.util.spec_from_file_location(nome, _OPS / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mde = _carrega("montar_dataset_multiescala")


# ── 1. Reprojeção ────────────────────────────────────────────────────────────
FRAME = (1000, 500)
CAIXA = {"class_name": "Luvas", "x_center": 0.4, "y_center": 0.4,
         "width": 0.1, "height": 0.1, "frame_id": "f"}


def test_reprojecao_com_caso_montado_a_mao():
    """Frame 1000×500, caixa 100×50 px centrada em (400,200); janela em (300,150)
    de 400×200. A caixa fica em (100,50) da janela → centro normalizado 0,25/0,25
    e lado 0,25/0,25. Números conferidos à mão, não gerados pelo próprio código."""
    r = mde.reprojetar(CAIXA, (300, 150, 400, 200), *FRAME)
    assert r is not None
    assert r["x_center"] == pytest.approx(0.25)
    assert r["y_center"] == pytest.approx(0.25)
    assert r["width"] == pytest.approx(0.25)
    assert r["height"] == pytest.approx(0.25)


def test_reprojecao_faz_o_objeto_CRESCER_que_e_o_ponto_do_script():
    """O objeto vale 56 px no frame inteiro e 140 px na janela de 0,4× — é
    exatamente a faixa de escala que falta no acervo."""
    lado = mde.LADO_MODELO
    assert CAIXA["width"] * FRAME[0] * lado / FRAME[0] == 56.0
    r = mde.reprojetar(CAIXA, (300, 150, 400, 200), *FRAME)
    assert r["width"] * lado == 140.0


def test_mutacao_offset_da_janela_reprova():
    """Se a reprojeção ESQUECESSE de subtrair a origem da janela (o erro clássico),
    o centro sairia 1,0 em vez de 0,25 — e a caixa cairia fora da imagem."""
    jx, jy, jw, jh = (300, 150, 400, 200)
    cx = CAIXA["x_center"] * FRAME[0]
    sem_offset = cx / jw                       # a MUTAÇÃO: sem `- jx`
    com_offset = (cx - jx) / jw
    assert sem_offset != pytest.approx(com_offset), "mutação não mudou nada"
    assert mde.reprojetar(CAIXA, (jx, jy, jw, jh), *FRAME)["x_center"] == pytest.approx(
        com_offset
    )


def test_caixa_cortada_ao_meio_e_descartada_nao_ensinada_mutilada():
    assert mde.reprojetar(CAIXA, (400, 150, 400, 200), *FRAME) is None
    assert mde.reprojetar(CAIXA, (700, 300, 300, 200), *FRAME) is None


def test_caixa_pouco_cortada_entra_e_encolhe_proporcionalmente():
    r = mde.reprojetar(CAIXA, (370, 150, 400, 200), *FRAME)
    assert r is not None and r["width"] == pytest.approx(80 / 400)


def test_janelas_sao_deterministicas_e_nao_emitem_janela_vazia():
    assert mde.janelas(*FRAME, [CAIXA], 0.4) == mde.janelas(*FRAME, [CAIXA], 0.4)
    assert mde.janelas(*FRAME, [], 0.4) == []


def test_sintetico_herda_o_grupo_do_pai_senao_o_split_vaza():
    """Filho no train com pai no val é leakage com cara de dado novo. O grupo do
    split é `video_id` ou `camera_id`+dia (`versioning_v2._group_key`)."""
    pai = {"id": "p1", "width": 1000, "height": 500, "camera_id": "cam-1",
           "captured_at": "2026-01-01T10:00:00", "video_id": None}
    saida = mde.sinteticos_do_frame(pai, [CAIXA], (0.4,))
    assert saida, "nenhum sintético gerado"
    for sint, anns, _janela in saida:
        assert sint["camera_id"] == pai["camera_id"]
        assert sint["captured_at"] == pai["captured_at"]
        assert sint["__pai__"] == "p1"
        assert all(a["frame_id"] == sint["id"] for a in anns)


# ── 2. Gabarito nunca vira treino ────────────────────────────────────────────
def _sql_do_pool() -> str:
    return (
        _RAIZ / "services" / "api" / "app" / "infrastructure" / "queue"
        / "tasks" / "versioning_v2.py"
    ).read_text(encoding="utf-8")


def test_o_caminho_do_pool_passa_pela_trava_de_holdout():
    """`carregar_pool` (usado por `preparar`) chama as MESMAS três funções do
    export de produção, e duas delas filtram `dataset_role = 'pool'`."""
    fonte = _sql_do_pool()
    assert fonte.count("tf.dataset_role = 'pool'") >= 2, (
        "a trava holdout-only sumiu de _snapshot_labeled_frames/_fetch_annotations"
    )
    mdv2 = (_OPS / "montar_dataset_v2.py").read_text(encoding="utf-8")
    for fn in ("_snapshot_labeled_frames", "_fetch_annotations"):
        assert fn in mdv2, f"{fn} não é mais a fonte do pool — a trava pode ter sumido"
    mult = (_OPS / "montar_dataset_multiescala.py").read_text(encoding="utf-8")
    assert "_mdv2.carregar_pool" in mult, (
        "o multi-escala parou de usar carregar_pool; se ele passar a ler "
        "training_frames direto, a trava de gabarito deixa de valer"
    )


def test_mutacao_trava_de_holdout_reprova():
    """A guarda acima só vale se ela reprovaria uma fonte SEM a trava."""
    fonte = _sql_do_pool()
    mutado = fonte.replace("tf.dataset_role = 'pool'", "TRUE")
    assert mutado != fonte, "mutação não mudou nada"
    assert mutado.count("tf.dataset_role = 'pool'") < 2


def test_sintetico_sem_pai_no_pool_nao_existe():
    """Não há caminho que crie recorte sintético de um frame fora do pool: os
    sintéticos saem SÓ dos frames que `carregar_pool` devolveu."""
    assert mde.sinteticos_do_frame(
        {"id": "x", "width": 1000, "height": 500}, [], (0.4,)
    ) == []


# ── 3. Taxonomia pública ─────────────────────────────────────────────────────
def test_no_glove_e_ausencia_nunca_o_epi():
    vd = mde._vd
    assert vd.MAPA["r1"]["no glove"] == ("ausencia", "Luvas")
    assert vd.destinos("ausencia", "Luvas", "b") == ("Sem Luvas",)
    assert vd.destinos("ausencia", "Luvas", "a") == ()   # ausência não é classe da A
    assert "Luvas" not in vd.destinos("ausencia", "Luvas", "b")


def test_mutacao_no_glove_para_Luvas_reprova():
    """A mutação que este teste existe para pegar: tratar `no glove` como
    PRESENÇA. Ela ensinaria o contrário do que a imagem mostra."""
    vd = mde._vd
    certo = vd.destinos(*vd.MAPA["r1"]["no glove"], "b")
    mutado = vd.destinos("presenca", "Luvas", "b")       # a MUTAÇÃO
    assert mutado == ("Luvas",)
    assert certo != mutado, "mutação não mudou nada"
    assert certo == ("Sem Luvas",)


def test_ausencia_nao_e_f_string_de_Sem_mais_o_nome():
    """`Protetor auditivo` vira `Sem protetor de ouvido`, não `Sem Protetor
    auditivo`: a segunda não existe no banco e criaria uma classe fantasma. É o
    caso que impede escrever o mapa como `f"Sem {epi}"`."""
    vd = mde._vd
    assert vd.AUSENCIA["Protetor auditivo"] == "Sem protetor de ouvido"
    assert f"Sem {'Protetor auditivo'}" not in set(vd.AUSENCIA.values())
    assert set(vd.AUSENCIA.values()) <= set(vd.classes_da_variante("b"))


def test_toda_classe_publica_emitida_existe_na_variante():
    vd = mde._vd
    for dataset, mapa in vd.MAPA.items():
        for nome, (tipo, alvo) in mapa.items():
            for variante in vd.VARIANTES:
                for d in vd.destinos(tipo, alvo, variante):
                    assert d in vd.classes_da_variante(variante), (dataset, nome, d)


# ── 4. Balanceamento ─────────────────────────────────────────────────────────
def test_peso_repete_quando_falta_e_subamostra_quando_sobra():
    assert mde.peso_de_dominio({"a": 100, "b": 900}, {"a": 0.5})["a"] == 5
    assert mde.peso_de_dominio({"a": 800, "b": 200}, {"a": 0.2})["a"] == pytest.approx(0.25)


def test_peso_respeita_o_teto_de_repeticao():
    """Repetir 194 caixas 20× é decorar — o defeito que o script diagnostica."""
    assert mde.peso_de_dominio({"a": 1, "b": 999}, {"a": 0.5}, max_repeticao=8)["a"] == 8


def test_subamostragem_e_por_imagem_e_prioriza_classe_escassa():
    ids = [f"i{n}" for n in range(10)]
    fica = mde.subamostrar(ids, 0.3, {"i7": 99, "i3": 98}, "s")
    assert len(fica) == 3
    assert {"i7", "i3"} <= fica
    assert fica == mde.subamostrar(ids, 0.3, {"i7": 99, "i3": 98}, "s")


def test_dominio_usa_o_lado_de_entrada_do_modelo_como_corte():
    assert mde.LIMITE_RECORTE_GRANDE == mde.LADO_MODELO
    assert mde.dominio({"id": "x", "width": 600, "height": 400}, set()) == "recorte-grande"
    assert mde.dominio({"id": "x", "width": 300, "height": 400}, set()) == "recorte-pequeno"
    assert mde.dominio({"id": "x", "width": 1920, "height": 1080}, {"x"}) == "quadro-cheio"


def test_autoteste_do_script_passa():
    assert mde.autoteste() == 0
