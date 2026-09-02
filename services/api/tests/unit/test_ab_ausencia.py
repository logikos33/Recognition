"""Testes do avaliador de ausência (`scripts/ops/ab_ausencia.py`).

Fixtures sintéticas: sem GPU, sem ONNX, detector mockado. O que se prova aqui é
a régua — contagem, derivação, acusação direta, guarda de vazamento e o que
acontece quando não houve predição nenhuma.
"""
import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "ops" / "ab_ausencia.py"


def _carregar():
    spec = importlib.util.spec_from_file_location("ab_ausencia", _SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ab = _carregar()


class DetectorFake:
    """Devolve uma saída canned por chamada, na ordem."""

    def __init__(self, saidas):
        self._saidas = list(saidas)
        self.chamadas = 0

    def predict(self, _frame):
        saida = self._saidas[min(self.chamadas, len(self._saidas) - 1)]
        self.chamadas += 1
        return list(saida)


def _det(classe, conf=0.9, bbox=(0, 0, 10, 10)):
    return {"class": classe, "confidence": conf, "bbox": list(bbox)}


def _coco(imagens, categorias, anotacoes):
    return {
        "images": [{"id": i, "file_name": n} for i, n in imagens],
        "categories": [{"id": i, "name": n} for i, n in categorias],
        "annotations": [
            {"id": k, "image_id": img, "category_id": cat, "bbox": [0, 0, 1, 1]}
            for k, (img, cat) in enumerate(anotacoes)
        ],
    }


def _escrever_coco(pasta: Path, nomes_arquivo, bytes_por_arquivo=None) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    coco = _coco([(i, n) for i, n in enumerate(nomes_arquivo)], [(0, "Luvas")], [])
    for nome in nomes_arquivo:
        conteudo = (bytes_por_arquivo or {}).get(nome, nome.encode())
        (pasta / nome).write_bytes(conteudo)
    caminho = pasta / "_annotations.coco.json"
    caminho.write_text(json.dumps(coco), encoding="utf-8")
    return caminho


# ── Contagem ──────────────────────────────────────────────────────────────────

def test_contagem_tp_fp_fn_com_resposta_conhecida():
    # universo 1..5; acusou 1,2,3; era real em 1,4  → TP={1} FP={2,3} FN={4}
    m = ab.contar(acusadas={1, 2, 3}, reais={1, 4}, universo={1, 2, 3, 4, 5})
    assert (m["tp"], m["fp"], m["fn"]) == (1, 2, 1)
    assert m["precisao"] == pytest.approx(1 / 3)
    assert m["recall"] == pytest.approx(1 / 2)
    assert m["n_acusacoes"] == 3
    assert m["n_reais"] == 2


def test_acusacao_fora_do_universo_nao_conta():
    """Imagem que falhou na leitura sai das DUAS variantes — não vira FP nem FN."""
    m = ab.contar(acusadas={1, 99}, reais={1, 98}, universo={1})
    assert (m["tp"], m["fp"], m["fn"]) == (1, 0, 0)


# ── Variante A: derivação pelo recorte de pessoa ──────────────────────────────

def test_variante_a_acusa_objeto_ausente_no_recorte():
    recortes = {
        # imagem 1: uma pessoa, com máscara e luvas — falta Óculos e Protetor
        1: [[_det("mascara"), _det("Luvas")]],
        # imagem 2: uma pessoa, com tudo
        2: [[_det("mascara"), _det("Luvas"), _det("Óculos"), _det("Protetor auditivo")]],
    }
    acusadas = ab.acusacoes_a(recortes, limiar=0.3)
    assert acusadas["Sem Óculos"] == {1}
    assert acusadas["Sem protetor de ouvido"] == {1}
    assert acusadas["Sem Luvas"] == set()
    assert acusadas["Sem mascara"] == set()


def test_variante_a_nao_acusa_imagem_sem_pessoa():
    """Sem recorte não há de quem falar — a acusação exige âncora."""
    assert ab.acusacoes_a({7: []}, limiar=0.3)["Sem Luvas"] == set()


def test_variante_a_acusa_tudo_quando_recorte_sai_vazio():
    """O preço da derivação: silêncio do detector vira acusação das 4 classes."""
    acusadas = ab.acusacoes_a({3: [[]]}, limiar=0.3)
    assert all(acusadas[c] == {3} for c in ab.MAPA_AUSENCIA.values())


def test_variante_a_respeita_o_limiar():
    """Objeto detectado ABAIXO do limiar conta como não detectado → acusa."""
    recortes = {1: [[_det("Luvas", conf=0.20)]]}
    assert ab.acusacoes_a(recortes, limiar=0.30)["Sem Luvas"] == {1}
    assert ab.acusacoes_a(recortes, limiar=0.15)["Sem Luvas"] == set()


# ── Variante B: classe direta ─────────────────────────────────────────────────

def test_variante_b_acusa_por_classe_direta_acima_do_limiar():
    dets = {
        1: [_det("Sem Luvas", conf=0.80), _det("Luvas", conf=0.95)],
        2: [_det("Sem Luvas", conf=0.10)],  # abaixo do limiar
        3: [_det("Uso incorreto de mascara", conf=0.60)],
    }
    acusadas = ab.acusacoes_b(dets, limiar=0.30)
    assert acusadas["Sem Luvas"] == {1}
    assert acusadas["Uso incorreto de mascara"] == {3}
    assert acusadas["Sem Óculos"] == set()


def test_gabarito_vem_das_anotacoes_sem_x_do_holdout():
    coco = _coco(
        imagens=[(1, "a.jpg"), (2, "b.jpg")],
        categorias=[(0, "Luvas"), (1, "Sem Luvas"), (2, "Sem Óculos")],
        anotacoes=[(1, 1), (1, 0), (2, 2)],
    )
    reais = ab.ausencias_reais(coco)
    assert reais["Sem Luvas"] == {1}
    assert reais["Sem Óculos"] == {2}
    assert reais["Sem mascara"] == set()


# ── Variante C: geometria do critério de sobreposição ─────────────────────────

# COCO [x, y, w, h]. A mão é grande, a luva é pequena e cabe dentro dela; a
# orelha é pequena e o abafador a engole. A relação de tamanho INVERTE entre os
# dois pares — é exatamente por isso que o critério é IoMin e não IoU.
MAO = [100, 100, 40, 40]          # área 1600
LUVA_NA_MAO = [110, 110, 15, 15]  # área  225, inteiramente dentro da mão
MAO_2 = [500, 100, 40, 40]        # outra pessoa, longe
ORELHA = [200, 200, 10, 10]       # área  100
ABAFADOR = [195, 195, 20, 20]     # área  400, engole a orelha


def test_iomin_e_1_quando_a_menor_esta_dentro_da_maior_nos_dois_sentidos():
    assert ab.sobreposicao(MAO, LUVA_NA_MAO) == pytest.approx(1.0)  # EPI menor
    assert ab.sobreposicao(ORELHA, ABAFADOR) == pytest.approx(1.0)  # EPI maior


def test_iou_puro_reprovaria_os_dois_pares_verdadeiros():
    """O argumento da escolha, escrito como teste: IoU aqui mede a coisa errada."""
    def iou(a, b):
        inter = ab.sobreposicao(a, b) * min(a[2] * a[3], b[2] * b[3])
        return inter / (a[2] * a[3] + b[2] * b[3] - inter)

    assert iou(MAO, LUVA_NA_MAO) < 0.5   # luva dentro da mão: 0.14
    assert iou(ORELHA, ABAFADOR) < 0.5   # abafador em volta da orelha: 0.25


def test_iomin_e_zero_para_caixas_disjuntas():
    assert ab.sobreposicao(MAO, MAO_2) == 0.0
    assert ab.sobreposicao(LUVA_NA_MAO, MAO_2) == 0.0


def test_iomin_nao_explode_com_caixa_degenerada():
    assert ab.sobreposicao([0, 0, 0, 0], MAO) == 0.0


# ── Variante C: acusação ──────────────────────────────────────────────────────

def _c(dets, limiar=0.30, sobrep=0.50):
    return ab.acusacoes_c({1: dets}, limiar, sobrep)


def test_variante_c_acusa_mao_sem_luva_sobreposta():
    acusadas, abstencoes = _c([_det("mão", bbox=MAO)])
    assert acusadas["Sem Luvas"] == {1}
    assert abstencoes["Sem Luvas"] == set()  # a âncora apareceu: houve julgamento


def test_variante_c_nao_acusa_mao_com_luva_sobreposta():
    acusadas, _ = _c([_det("mão", bbox=MAO), _det("luva", bbox=LUVA_NA_MAO)])
    assert acusadas["Sem Luvas"] == set()


def test_variante_c_nao_deixa_a_luva_de_uma_pessoa_cobrir_a_mao_da_outra():
    """Duas pessoas na cena: a luva está em cima da mão 1, a mão 2 está nua."""
    acusadas, _ = _c([
        _det("mão", bbox=MAO), _det("luva", bbox=LUVA_NA_MAO), _det("mão", bbox=MAO_2),
    ])
    assert acusadas["Sem Luvas"] == {1}


def test_variante_c_com_epi_que_nao_sobrepoe_nenhuma_parte_acusa():
    """Luva detectada solta no canto não inocenta a mão que está do outro lado."""
    acusadas, _ = _c([_det("mão", bbox=MAO), _det("luva", bbox=[900, 900, 15, 15])])
    assert acusadas["Sem Luvas"] == {1}


def test_variante_c_duas_maos_uma_com_luva_outra_sem_acusa():
    acusadas, _ = _c([
        _det("mão", bbox=MAO),
        _det("luva", bbox=LUVA_NA_MAO),
        _det("mão", bbox=[300, 100, 40, 40]),
    ])
    assert acusadas["Sem Luvas"] == {1}


def test_variante_c_duas_maos_ambas_com_luva_nao_acusa():
    acusadas, _ = _c([
        _det("mão", bbox=MAO), _det("luva", bbox=LUVA_NA_MAO),
        _det("mão", bbox=[300, 100, 40, 40]), _det("luva", bbox=[310, 110, 15, 15]),
    ])
    assert acusadas["Sem Luvas"] == set()


def test_variante_c_orelha_sem_abafador_acusa_e_com_abafador_nao():
    acusadas, _ = _c([_det("orelha", bbox=ORELHA)])
    assert acusadas["Sem protetor de ouvido"] == {1}
    acusadas, _ = _c([
        _det("orelha", bbox=ORELHA), _det("protetor auricular", bbox=ABAFADOR)
    ])
    assert acusadas["Sem protetor de ouvido"] == set()


def test_variante_c_rosto_serve_de_ancora_para_mascara_e_oculos():
    rosto = [50, 50, 100, 120]
    acusadas, _ = _c([_det("rosto", bbox=rosto), _det("máscara", bbox=[70, 100, 60, 40])])
    assert acusadas["Sem mascara"] == set()
    assert acusadas["Sem Óculos"] == {1}  # mesma âncora, EPI diferente


def test_variante_c_respeita_o_limiar_de_sobreposicao():
    """Luva meio dentro, meio fora: acusa a 0,90 e não acusa a 0,25."""
    meia_luva = [125, 110, 30, 15]  # metade da área cai fora da mão
    assert ab.sobreposicao(MAO, meia_luva) == pytest.approx(0.5)
    assert _c([_det("mão", bbox=MAO), _det("luva", bbox=meia_luva)], sobrep=0.90)[0][
        "Sem Luvas"] == {1}
    assert _c([_det("mão", bbox=MAO), _det("luva", bbox=meia_luva)], sobrep=0.25)[0][
        "Sem Luvas"] == set()


def test_variante_c_respeita_o_limiar_de_confianca():
    abaixo = [_det("mão", bbox=MAO, conf=0.10)]
    acusadas, abstencoes = _c(abaixo, limiar=0.30)
    assert acusadas["Sem Luvas"] == set()
    assert abstencoes["Sem Luvas"] == {1}  # âncora abaixo do limiar = não detectada


# ── Variante C: ausência de evidência ≠ acusação ──────────────────────────────

def test_variante_c_sem_parte_do_corpo_e_abstencao_nao_acusacao():
    acusadas, abstencoes = _c([])
    assert all(acusadas[c] == set() for c in ab.CLASSES_AUSENCIA)
    assert abstencoes["Sem Luvas"] == {1}


def test_variante_c_epi_sem_parte_do_corpo_tambem_e_abstencao():
    """Falha do detector de parte: vejo a luva mas não a mão. Não sei de quem falar."""
    acusadas, abstencoes = _c([_det("luva", bbox=LUVA_NA_MAO)])
    assert acusadas["Sem Luvas"] == set()
    assert abstencoes["Sem Luvas"] == {1}


def test_variante_c_abstem_por_classe_nao_pela_imagem_inteira():
    """Mão detectada, orelha não: julga luva, abstém-se de protetor."""
    acusadas, abstencoes = _c([_det("mão", bbox=MAO)])
    assert acusadas["Sem Luvas"] == {1} and abstencoes["Sem Luvas"] == set()
    assert acusadas["Sem protetor de ouvido"] == set()
    assert abstencoes["Sem protetor de ouvido"] == {1}


def test_variante_c_abstem_de_uso_incorreto_de_mascara():
    """Máscara sobreposta ao rosto não diz se está no queixo. C não tem mecanismo."""
    _, abstencoes = _c([_det("rosto", bbox=[50, 50, 100, 120])])
    assert abstencoes[ab.CLASSE_SO_DIRETA] == {1}


def test_abstencao_nao_vira_tp_nem_fp():
    """A prova de que ausência de evidência não entra na conta de acusação."""
    m = ab.contar(acusadas=set(), reais={1}, universo={1, 2}, abstencoes={1, 2})
    assert (m["tp"], m["fp"]) == (0, 0)
    assert m["precisao"] is None  # não houve acusação para julgar
    assert m["abstencoes"] == 2
    assert m["taxa_abstencao"] == 1.0
    assert m["fn"] == 1 and m["fn_por_abstencao"] == 1  # a perda foi por cegueira


def test_fn_por_abstencao_separa_cegueira_de_julgamento_errado():
    # imagem 1: absteve-se e a ausência era real  → FN por abstenção
    # imagem 2: julgou, não acusou, era real      → FN por julgamento
    m = ab.contar(acusadas=set(), reais={1, 2}, universo={1, 2}, abstencoes={1})
    assert m["fn"] == 2
    assert m["fn_por_abstencao"] == 1


def test_abstencoes_a_marca_imagem_sem_pessoa():
    abst = ab.abstencoes_a({1: [], 2: [[_det("Luvas")]]})
    assert abst["Sem Luvas"] == {1}
    assert abst[ab.CLASSE_SO_DIRETA] == {1, 2}  # A nunca vê "uso incorreto"


def test_conferir_dicionario_c_recusa_nomes_incompativeis():
    """Dicionário errado faria C abstender-se em 100% e parecer cautelosa."""
    with pytest.raises(SystemExit) as exc:
        ab.conferir_dicionario_c(["Luvas", "Sem Luvas"])
    assert "incompatível" in str(exc.value)
    ab.conferir_dicionario_c(
        ["pessoa", "mão", "luva", "rosto", "máscara", "óculos", "orelha",
         "protetor auricular", "botas"]
    )  # não levanta


# ── Divisão por zero ──────────────────────────────────────────────────────────

def test_classe_sem_predicao_nao_explode_nem_vira_precisao_100():
    m = ab.contar(acusadas=set(), reais=set(), universo={1, 2, 3})
    assert m["precisao"] is None  # não é 1.0: "acertou todas as zero" não é acerto
    assert m["recall"] is None
    assert ab._pct(m["precisao"]) == "—"
    assert ab.sustenta_acusacao(m) is False


def test_classe_com_reais_mas_sem_acusacao_tem_recall_zero_e_precisao_indefinida():
    m = ab.contar(acusadas=set(), reais={1, 2}, universo={1, 2, 3})
    assert m["precisao"] is None
    assert m["recall"] == 0.0
    assert m["fn"] == 2


# ── Régua ADR-0067 e veredito ─────────────────────────────────────────────────

def _metrica(tp, fp, fn):
    return ab.contar(
        acusadas=set(range(tp + fp)),
        reais=set(range(tp)) | set(range(1000, 1000 + fn)),
        universo=set(range(tp + fp)) | set(range(1000, 1000 + fn)),
    )


def test_regua_reprova_precisao_abaixo_de_50_por_cento():
    assert ab.sustenta_acusacao(_metrica(tp=20, fp=40, fn=5)) is False


def test_regua_reprova_n_insuficiente_mesmo_com_precisao_alta():
    """ADR-0067: 66,7% sobre 3 propostas é sorte, não evidência."""
    assert ab.sustenta_acusacao(_metrica(tp=2, fp=1, fn=0)) is False


def test_empate_tecnico_vence_a_mais_simples():
    a = _metrica(tp=60, fp=40, fn=40)
    b = _metrica(tp=61, fp=39, fn=40)
    assert ab.vencedor_classe({"A": a, "B": b})[0] == "A"


def test_veredito_nao_inventa_vencedor_quando_ninguem_sustenta():
    ruim = _metrica(tp=10, fp=90, fn=10)
    vencedor, motivo = ab.vencedor_classe({"A": ruim, "B": ruim})
    assert vencedor is None
    assert motivo == "nenhuma sustenta a régua"


def test_b_vence_quando_so_ela_sustenta_a_regua():
    a = _metrica(tp=10, fp=90, fn=10)
    b = _metrica(tp=80, fp=20, fn=10)
    assert ab.vencedor_classe({"A": a, "B": b})[0] == "B"


def test_c_entra_no_veredito_e_vence_quando_e_a_unica_que_sustenta():
    ruim = _metrica(tp=10, fp=90, fn=10)
    boa = _metrica(tp=80, fp=20, fn=10)
    assert ab.vencedor_classe({"A": ruim, "B": ruim, "C": boa})[0] == "C"


def test_empate_a_tres_vence_a_mais_simples_declarada():
    m = _metrica(tp=70, fp=30, fn=30)
    vencedor, motivo = ab.vencedor_classe({"A": m, "B": m, "C": m})
    assert vencedor == "A"
    assert "empate técnico" in motivo


def test_veredito_geral_conta_vitorias_das_tres():
    assert ab.veredito_geral({"x": "C", "y": "C", "z": "B"}).startswith("C vence")
    assert ab.veredito_geral({"x": None, "y": None}).startswith("SEM VEREDITO")
    assert "vence a mais simples: B" in ab.veredito_geral({"x": "B", "y": "C"})


# ── Guarda de vazamento ───────────────────────────────────────────────────────

def test_guard_vazamento_falha_por_nome(tmp_path):
    holdout = _escrever_coco(tmp_path / "hold", ["f1.jpg", "f2.jpg"])
    treino = _escrever_coco(tmp_path / "train", ["f2.jpg", "f3.jpg"])
    with pytest.raises(SystemExit) as exc:
        ab.verificar_vazamento(holdout, [treino])
    assert "VAZAMENTO DE HOLDOUT" in str(exc.value)


def test_guard_vazamento_falha_por_conteudo_mesmo_com_nome_diferente(tmp_path):
    """Reexportar a mesma imagem com outro nome não a torna outra imagem."""
    mesmos_bytes = b"\x89PNG-conteudo-identico"
    holdout = _escrever_coco(tmp_path / "hold", ["a.jpg"], {"a.jpg": mesmos_bytes})
    treino = _escrever_coco(tmp_path / "train", ["zzz.jpg"], {"zzz.jpg": mesmos_bytes})
    with pytest.raises(SystemExit) as exc:
        ab.verificar_vazamento(holdout, [treino])
    assert "MESMO CONTEÚDO" in str(exc.value)


def test_guard_passa_quando_holdout_e_treino_sao_disjuntos(tmp_path):
    holdout = _escrever_coco(tmp_path / "hold", ["h1.jpg", "h2.jpg"])
    treino = _escrever_coco(tmp_path / "train", ["t1.jpg", "t2.jpg"])
    r = ab.verificar_vazamento(holdout, [treino])
    assert r["colisoes_nome"] == [] and r["colisoes_hash"] == []
    assert r["holdout_hasheadas"] == 2 and r["treino_hasheadas"] == 2


# ── Laço de inferência (detector mockado, imagens reais em disco) ─────────────

def test_inferir_holdout_recorta_pessoa_e_da_o_mesmo_universo_para_as_duas(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    for nome in ("i1.jpg", "i2.jpg"):
        cv2.imwrite(str(tmp_path / nome), np.full((100, 100, 3), 128, dtype=np.uint8))
    coco = _coco(
        imagens=[(1, "i1.jpg"), (2, "i2.jpg"), (3, "sumida.jpg")],
        categorias=[(0, "Luvas"), (1, "Sem Luvas")],
        anotacoes=[(1, 1)],
    )

    det_pessoa = DetectorFake([[_det("person", bbox=(10, 10, 40, 60))], []])
    det_a = DetectorFake([[_det("mascara")]])  # só máscara no recorte → falta o resto
    det_b = DetectorFake([[_det("Sem Luvas", conf=0.7)], []])
    det_c = DetectorFake([[_det("mão", bbox=MAO)], []])

    universo, saidas, recortes_a, falhas = ab.inferir_holdout(
        coco, tmp_path, det_a, det_pessoa, "person", {"B": det_b, "C": det_c}
    )

    assert universo == {1, 2}  # a imagem 3 não existe → fora das TRÊS
    assert len(falhas) == 1 and "sumida.jpg" in falhas[0]
    assert len(recortes_a[1]) == 1 and recortes_a[2] == []
    assert det_a.chamadas == 1  # só houve pessoa na imagem 1
    assert set(saidas["B"]) == set(saidas["C"]) == universo  # mesma prova para todas

    reais = ab.ausencias_reais(coco)
    medidas = ab.medir_todas(recortes_a, saidas, reais, universo, 0.3, 0.5)
    assert set(medidas) == {"A", "B", "C"}
    for variante in ("A", "B", "C"):
        m = medidas[variante]["Sem Luvas"]
        assert (m["tp"], m["fp"]) == (1, 0), variante
    # a imagem 2 não tem pessoa (A) nem mão (C) → abstenção, não acusação
    assert medidas["A"]["Sem Luvas"]["abstencoes"] == 1
    assert medidas["C"]["Sem Luvas"]["abstencoes"] == 1
    assert medidas["B"]["Sem Luvas"]["abstencoes"] == 0  # B não tem abstenção


def test_guard_conta_arquivos_hasheados_nao_hashes_distintos(tmp_path):
    """Duas imagens idênticas não podem virar 'uma não está no disco' no relatório."""
    iguais = b"conteudo-repetido"
    holdout = _escrever_coco(
        tmp_path / "hold", ["a.jpg", "b.jpg"], {"a.jpg": iguais, "b.jpg": iguais}
    )
    treino = _escrever_coco(tmp_path / "train", ["t.jpg"])
    assert ab.verificar_vazamento(holdout, [treino])["holdout_hasheadas"] == 2


def test_main_fim_a_fim_escreve_relatorio(tmp_path, monkeypatch, capsys):
    """O relatório inteiro (tabelas + varredura + veredito) renderiza sem GPU."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    hold = tmp_path / "hold"
    hold.mkdir()
    for nome in ("h1.jpg", "h2.jpg"):
        cv2.imwrite(str(hold / nome), np.full((80, 80, 3), 200, dtype=np.uint8))
    coco = _coco(
        imagens=[(1, "h1.jpg"), (2, "h2.jpg")],
        categorias=[(0, "Luvas"), (1, "Sem Luvas"), (2, "Uso incorreto de mascara")],
        anotacoes=[(1, 1), (2, 2)],
    )
    (hold / "_annotations.coco.json").write_text(json.dumps(coco), encoding="utf-8")
    treino = _escrever_coco(tmp_path / "train", ["t1.jpg"])

    fakes = {
        "a": DetectorFake([[_det("Luvas")]]),
        "pessoa": DetectorFake([[_det("person", bbox=(5, 5, 40, 60))]]),
        "b": DetectorFake([[_det("Sem Luvas", conf=0.7)]]),
        "c": DetectorFake([[_det("mão", bbox=MAO), _det("orelha", bbox=ORELHA)]]),
    }
    ordem = iter(("a", "pessoa", "b", "c"))  # ordem de construção em main()
    monkeypatch.setattr(ab, "_construir_detector", lambda *a, **k: fakes[next(ordem)])

    saida = tmp_path / "rel.md"
    assert ab.main([
        "--holdout", str(hold / "_annotations.coco.json"),
        "--modelo-a", "a.onnx", "--modelo-b", "b.onnx", "--modelo-c", "c.onnx",
        "--pessoa", "p.onnx", "--treino", str(treino), "--saida", str(saida),
        "--classes-c", "pessoa,mão,luva,rosto,máscara,óculos,orelha,"
                       "protetor auricular,botas",
    ]) == 0

    texto = saida.read_text(encoding="utf-8")
    assert "Guarda de vazamento" in texto
    assert "Sem protetor de ouvido" in texto  # todas as classes de ausência na tabela
    assert "Varredura de limiares de confiança" in texto
    assert "Varredura do limiar de SOBREPOSIÇÃO" in texto
    assert "IoMin" in texto and "abstenção" in texto
    assert "C · sobreposição geométrica" in texto  # as três na mesma tabela
    assert "O que este relatório NÃO mediu" in texto
    assert "veredito geral" in capsys.readouterr().out


def test_main_sem_modelo_c_sai_so_com_a_e_b(tmp_path, monkeypatch):
    """C é opcional — o script continua servindo antes de a variante existir."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    hold = tmp_path / "hold"
    hold.mkdir()
    cv2.imwrite(str(hold / "h1.jpg"), np.full((80, 80, 3), 200, dtype=np.uint8))
    (hold / "_annotations.coco.json").write_text(
        json.dumps(_coco([(1, "h1.jpg")], [(0, "Luvas"), (1, "Sem Luvas")], [(1, 1)])),
        encoding="utf-8",
    )
    treino = _escrever_coco(tmp_path / "train", ["t1.jpg"])

    fakes = iter([
        DetectorFake([[_det("Luvas")]]),
        DetectorFake([[_det("person", bbox=(5, 5, 40, 60))]]),
        DetectorFake([[_det("Sem Luvas", conf=0.7)]]),
    ])
    monkeypatch.setattr(ab, "_construir_detector", lambda *a, **k: next(fakes))

    saida = tmp_path / "rel.md"
    assert ab.main([
        "--holdout", str(hold / "_annotations.coco.json"),
        "--modelo-a", "a.onnx", "--modelo-b", "b.onnx", "--pessoa", "p.onnx",
        "--treino", str(treino), "--saida", str(saida),
    ]) == 0
    texto = saida.read_text(encoding="utf-8")
    assert "C · sobreposição geométrica" not in texto
    assert "Varredura do limiar de SOBREPOSIÇÃO" not in texto


def test_main_falha_ruidosamente_com_vazamento(tmp_path):
    """Guarda ANTES da inferência: prova contaminada não gasta GPU."""
    holdout = _escrever_coco(tmp_path / "hold", ["x.jpg"])
    treino = _escrever_coco(tmp_path / "train", ["x.jpg"])
    with pytest.raises(SystemExit) as exc:
        ab.main([
            "--holdout", str(holdout), "--modelo-a", "a.onnx", "--modelo-b", "b.onnx",
            "--pessoa", "p.onnx", "--treino", str(treino),
            "--saida", str(tmp_path / "nunca.md"),
        ])
    assert "VAZAMENTO DE HOLDOUT" in str(exc.value)
    assert not (tmp_path / "nunca.md").exists()


def test_recortar_aplica_margem_do_edge_e_recusa_recorte_degenerado():
    np = pytest.importorskip("numpy")
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    recorte = ab.recortar(frame, [50, 50, 40, 20])
    # margem 25% em x (10px de cada lado) e 8% em y (1px)
    assert recorte.shape[:2] == (20 + 2, 40 + 20)
    assert ab.recortar(frame, [0, 0, 0, 0]) is None
