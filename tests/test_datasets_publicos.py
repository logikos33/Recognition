"""O mapeamento dos datasets públicos não pode mentir em silêncio.

Nenhum teste aqui baixa coisa alguma: as fixtures são sintéticas.

O teste-chave é `TestAusenciaNuncaViraPresenca`. Ele existe porque o erro que
mais barato passa despercebido neste código é mandar `no glove` para `Luvas`:
o volume sobe, o relatório fica bonito, e o modelo aprende que mão nua é mão
com luva — a inversão exata do que o cliente precisa detectar.

Por isso a lista de classes públicas que significam AUSÊNCIA está escrita à mão
aqui, copiada da lista de classes declarada por cada dataset. Se ela fosse
derivada de `MAPA`, o teste leria a verdade do próprio código que testa e
aprovaria qualquer inversão.
"""

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[1]


def _carrega(nome: str):
    spec = importlib.util.spec_from_file_location(nome, _RAIZ / "scripts" / "ops" / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod
    spec.loader.exec_module(mod)
    return mod


conv = _carrega("converter_datasets_publicos")
baixa = _carrega("baixar_datasets_publicos")


#: Classes públicas que significam AUSÊNCIA de EPI. Escritas à mão a partir da
#: lista de classes declarada na página de cada dataset — NÃO derivadas do MAPA.
AUSENCIA_PUBLICA = {
    "r1": ["no mask", "no earmuff", "no glove"],
    "r2": ["No_Glove", "No_Goggles", "No_Shoe", "No_Helmet", "No_Harness", "No_BreathingApparatus"],
    "r3": ["NO-Gloves"],
    "r6": ["hand_noglove", "face_nomask", "head_nohelmet"],
}

#: Classes da variante C que afirmam que o EPI ESTÁ presente.
EPI_DA_VARIANTE_C = {"luva", "oculos", "mascara", "protetor_auricular", "botas", "mascara_incorreta"}


def _anns(*nomes: str) -> list[dict]:
    return [
        {"class_name": n, "image_id": i, "bbox": [10.0, 20.0, 30.0, 40.0]}
        for i, n in enumerate(nomes)
    ]


def _nomes(saida: list[dict]) -> list[str]:
    return [a["category_name"] for a in saida]


# ── 1. o mapeamento leva cada classe para onde diz que leva ──────────────────
class TestLevaOndeDiz:
    @pytest.mark.parametrize(
        ("dataset", "publica", "variante", "esperado"),
        [
            ("r1", "gloves", "a", ["Luvas"]),
            ("r1", "earmuff", "a", ["Protetor auditivo"]),
            ("r1", "mask", "a", ["mascara"]),
            ("r2", "Goggles", "a", ["Óculos"]),
            ("r6", "boots", "a", ["Botas"]),
            # a ausência usa a grafia EXATA do banco, que é irregular
            ("r1", "no earmuff", "b", ["Sem protetor de ouvido"]),
            ("r1", "no glove", "b", ["Sem Luvas"]),
            ("r2", "No_Goggles", "b", ["Sem Óculos"]),
            ("r6", "face_nomask", "b", ["Sem mascara"]),
            # C: a caixa de EPI vira DUAS (parte do corpo + EPI)
            ("r1", "gloves", "c", ["mao", "luva"]),
            ("r1", "earmuff", "c", ["orelha", "protetor_auricular"]),
            ("r2", "Goggles", "c", ["regiao_olhos", "oculos"]),
            # C: a caixa de ausência vira SÓ a parte do corpo
            ("r1", "no glove", "c", ["mao"]),
            ("r3", "NO-Gloves", "c", ["mao"]),
            # OID só existe na C
            ("oid", "Human hand", "c", ["mao"]),
            ("oid", "Human ear", "c", ["orelha"]),
            ("oid", "Human face", "c", ["rosto"]),
        ],
    )
    def test_destino(self, dataset, publica, variante, esperado):
        saida, contas = conv.converter(_anns(publica), dataset, variante)
        assert _nomes(saida) == esperado
        assert contas["emitidas"] == len(esperado)

    def test_nome_de_ausencia_nao_e_inventado(self):
        """`Protetor auditivo` vira `Sem protetor de ouvido`, não `Sem Protetor auditivo`.

        Um f-string ingênuo criaria uma 6ª classe que não existe no banco.
        """
        saida, _ = conv.converter(_anns("no earmuff"), "r1", "b")
        assert _nomes(saida) == ["Sem protetor de ouvido"]
        assert "Sem Protetor auditivo" not in conv.classes_da_variante("b")

    def test_bbox_e_image_id_atravessam_intactos(self):
        saida, _ = conv.converter(_anns("gloves"), "r1", "c")
        assert all(a["bbox"] == [10.0, 20.0, 30.0, 40.0] for a in saida)
        assert {a["image_id"] for a in saida} == {0}

    def test_category_id_bate_com_as_categorias_coco(self):
        saida, _ = conv.converter(_anns("gloves", "earmuff"), "r1", "c")
        por_id = {c["id"]: c["name"] for c in conv.categorias("c")}
        assert por_id[0] == conv._vc.ANCORA, "id 0 é a âncora que o RF-DETR do produto espera"
        for a in saida:
            assert por_id[a["category_id"]] == a["category_name"]


# ── 2. classe não mapeada é descartada E CONTADA ─────────────────────────────
class TestDescarteEContado:
    def test_fora_da_taxonomia_some_mas_aparece_no_numero(self):
        saida, contas = conv.converter(_anns("Helmet", "Helmet", "Glove"), "r2", "a")
        assert _nomes(saida) == ["Luvas"]
        assert contas["descartadas"] == 2
        assert contas["por_classe"]["Helmet"] == {
            "tipo": "fora",
            "alvo": contas["por_classe"]["Helmet"]["alvo"],
            "entrada": 2,
            "emitidas": 0,
            "descartadas": 2,
            "motivo": contas["por_classe"]["Helmet"]["alvo"],
        }
        assert "taxonomia RVB" in contas["por_classe"]["Helmet"]["motivo"]

    def test_descarte_da_variante_tambem_e_contado(self):
        """Descartar ausência na A é legítimo — e mesmo assim entra na conta."""
        _, contas = conv.converter(_anns("no glove", "gloves"), "r1", "a")
        assert contas["descartadas"] == 1
        assert contas["por_classe"]["no glove"]["descartadas"] == 1
        assert "variante A" in contas["por_classe"]["no glove"]["motivo"]

    def test_classe_desconhecida_nao_some_calada(self):
        """Classe que o export tem e a tabela não: sinal, não descarte silencioso."""
        saida, contas = conv.converter(_anns("classe_nova_do_export"), "r1", "a")
        assert saida == []
        assert contas["classes_desconhecidas"] == {"classe_nova_do_export": 1}
        assert "CLASSE FORA DA TABELA" in conv.relatorio(contas)

    def test_toda_entrada_e_contabilizada(self):
        """entrada = emitidas-de-origem + descartadas + desconhecidas. Nada evapora."""
        entrada = _anns("gloves", "no glove", "mask", "inexistente")
        _, contas = conv.converter(entrada, "r1", "b")
        com_origem = sum(1 for c in contas["por_classe"].values() if c["emitidas"])
        assert com_origem  # sanidade
        vistas = sum(c["entrada"] for c in contas["por_classe"].values())
        assert vistas + sum(contas["classes_desconhecidas"].values()) == len(entrada)

    def test_relatorio_mostra_o_n(self):
        _, contas = conv.converter(_anns("Helmet", "Glove"), "r2", "a")
        texto = conv.relatorio(contas)
        assert "n=1" in texto and "descartadas=1" in texto and "Helmet" in texto


# ── 3. as três variantes saem DIFERENTES do mesmo insumo ─────────────────────
class TestTresVariantesDoMesmoInsumo:
    def test_mesmo_insumo_tres_saidas_distintas(self):
        entrada = _anns("gloves", "no glove", "earmuff", "no earmuff")
        a, b, c = (conv.converter(entrada, "r1", v)[0] for v in "abc")
        assert _nomes(a) == ["Luvas", "Protetor auditivo"]
        assert _nomes(b) == ["Luvas", "Sem Luvas", "Protetor auditivo", "Sem protetor de ouvido"]
        assert _nomes(c) == [
            "mao", "luva", "mao", "orelha", "protetor_auricular", "orelha",
        ]
        assert len({tuple(_nomes(x)) for x in (a, b, c)}) == 3

    def test_espacos_de_classe_nao_se_confundem(self):
        assert len(conv.classes_da_variante("a")) == 5
        assert len(conv.classes_da_variante("b")) == 10
        assert set(conv.classes_da_variante("a")) < set(conv.classes_da_variante("b"))

    def test_a_sobreposicao_de_nomes_entre_B_e_C_esta_fixada(self):
        """Armadilha real, medida: os espaços de classe QUASE não se tocam.

        B∩C = {'mascara'} — mesma string, mesmo objeto. E `Botas` (B) difere de
        `botas` (C) SÓ NA CAIXA ALTA: qualquer `.lower()` no caminho funde as
        duas sem erro nenhum. Os nomes vêm de converter_variante_c.py, não daqui;
        o teste fixa o estado para que a sobreposição não CRESÇA em silêncio e
        contamine a comparação A/B/C.
        """
        b, c = set(conv.classes_da_variante("b")), set(conv.classes_da_variante("c"))
        assert b & c == {"mascara"}
        assert {x.lower() for x in b} & {x.lower() for x in c} == {"mascara", "botas"}

    def test_variante_c_e_a_mesma_do_rvb_mais_as_extras_declaradas(self):
        """Se divergir de converter_variante_c.py, o pré-treino não concatena."""
        assert set(conv.classes_da_variante("c")) == (
            set(conv._vc.CLASSES) | set(conv.PARTES_SO_PUBLICAS)
        )

    def test_oid_so_alimenta_a_c_e_o_zero_e_declarado(self):
        entrada = _anns("Human hand", "Human face", "Human ear")
        for v in ("a", "b"):
            saida, contas = conv.converter(entrada, "oid", v)
            assert saida == [], f"OID não tem classe de EPI; variante {v} tem de sair vazia"
            assert contas["descartadas"] == 3, "vazio medido, não vazio por acidente"
        assert len(conv.converter(entrada, "oid", "c")[0]) == 3

    def test_variante_invalida_explode(self):
        with pytest.raises(ValueError, match="variante"):
            conv.converter(_anns("gloves"), "r1", "d")


# ── 4. A TRAVA: ausência nunca vira presença ─────────────────────────────────
class TestAusenciaNuncaViraPresenca:
    """Mutação alvo: mandar `no glove` para `Luvas`. Estes testes têm de reprovar."""

    @pytest.mark.parametrize(
        ("dataset", "publica"),
        [(d, p) for d, ps in AUSENCIA_PUBLICA.items() for p in ps],
    )
    def test_nenhuma_variante_afirma_o_epi(self, dataset, publica):
        for variante in ("a", "b", "c"):
            emitidas = set(_nomes(conv.converter(_anns(publica), dataset, variante)[0]))
            assert not emitidas & set(conv.PRESENCA), (
                f"{dataset}/{publica} emitiu presença {emitidas & set(conv.PRESENCA)} "
                f"na variante {variante} — inverteria o significado"
            )
            assert not emitidas & EPI_DA_VARIANTE_C, (
                f"{dataset}/{publica} emitiu EPI {emitidas & EPI_DA_VARIANTE_C} "
                f"na variante {variante} — a derivação por sobreposição leria conformidade"
            )

    @pytest.mark.parametrize(
        ("dataset", "publica"),
        [(d, p) for d, ps in AUSENCIA_PUBLICA.items() for p in ps],
    )
    def test_na_variante_a_ausencia_nao_e_classe(self, dataset, publica):
        """ADR-0065/0067: na A a ausência sai do recorte de pessoa, não do detector."""
        saida, contas = conv.converter(_anns(publica), dataset, "a")
        assert saida == []
        assert contas["descartadas"] == 1

    @pytest.mark.parametrize(
        ("dataset", "publica"),
        [(d, p) for d, ps in AUSENCIA_PUBLICA.items() for p in ps],
    )
    def test_na_variante_b_ou_vira_Sem_X_ou_e_descartada(self, dataset, publica):
        emitidas = _nomes(conv.converter(_anns(publica), dataset, "b")[0])
        assert all(n.startswith("Sem ") for n in emitidas), emitidas
        assert set(emitidas) <= set(conv.AUSENCIA.values())

    @pytest.mark.parametrize(
        ("dataset", "publica"),
        [(d, p) for d, ps in AUSENCIA_PUBLICA.items() for p in ps],
    )
    def test_na_variante_c_so_sai_parte_do_corpo(self, dataset, publica):
        emitidas = _nomes(conv.converter(_anns(publica), dataset, "c")[0])
        assert all(n in conv._vc.PROTEGE or n in conv.PARTES_SO_PUBLICAS for n in emitidas), emitidas

    def test_o_rosto_inteiro_nao_colapsa_nas_duas_regioes(self):
        """`Human face` cobre as duas; virar uma delas seria geometria inventada."""
        emitidas = _nomes(conv.converter(_anns("Human face"), "oid", "c")[0])
        assert emitidas == ["rosto"]
        assert "regiao_olhos" not in emitidas and "regiao_boca_nariz" not in emitidas
        assert "rosto" in conv.PARTES_SO_PUBLICAS


# ── 5. procedência e licença ficam gravadas junto do dado ────────────────────
class TestProcedencia:
    def test_grava_licenca_url_e_atribuicao_ao_lado_do_dado(self, tmp_path):
        fonte = next(f for f in baixa.ROBOFLOW if f["id"] == "r1")
        baixa.grava_procedencia(tmp_path, fonte, {"sha256": "abc", "completo": True})
        registro = json.loads((tmp_path / "PROCEDENCIA.json").read_text())
        assert registro["licenca"] == "CC BY 4.0"
        assert registro["licenca_url"].startswith("https://creativecommons.org/licenses/by/4.0")
        assert registro["url"].startswith("https://universe.roboflow.com/")
        assert registro["sha256"] == "abc"
        assert "baixado_em" in registro
        texto = (tmp_path / "ATRIBUICAO.txt").read_text()
        assert "CC BY 4.0" in texto and fonte["nome"] in texto and fonte["url"] in texto

    def test_cc0_dispensa_credito_mas_registra(self, tmp_path):
        fonte = next(f for f in baixa.ROBOFLOW if f["id"] == "r6")
        baixa.grava_procedencia(tmp_path, fonte, {"completo": True})
        assert "domínio público" in (tmp_path / "ATRIBUICAO.txt").read_text()

    def test_gate_reprova_licenca_divergente(self):
        with pytest.raises(RuntimeError, match="LICENÇA DIVERGENTE"):
            baixa._confere_licenca("CC BY-NC-SA 4.0", "CC BY 4.0", "r1")

    def test_gate_reprova_licenca_ausente(self):
        with pytest.raises(RuntimeError, match="não devolveu campo de licença"):
            baixa._confere_licenca(None, "CC BY 4.0", "r1")

    def test_sh17_nao_esta_entre_as_fontes(self):
        """CC BY-NC-SA 4.0. A taxonomia pode ser copiada; o dado, não."""
        assert "sh17" not in json.dumps(baixa.ROBOFLOW).lower()
        assert all("noncommercial" not in f["licenca_url"].lower() for f in baixa.ROBOFLOW)

    def test_toda_fonte_tem_licenca_comercial_declarada(self):
        for f in [*baixa.ROBOFLOW, baixa.OID]:
            assert f["licenca"] in ("CC BY 4.0", "Public Domain"), f
            assert "/nc" not in f["licenca_url"] and "-nc" not in f["licenca_url"]

    def test_idempotencia_so_conta_download_completo(self, tmp_path):
        fonte = baixa.ROBOFLOW[0]
        assert baixa.ja_baixado(tmp_path) is False
        baixa.grava_procedencia(tmp_path, fonte, {"completo": False})
        assert baixa.ja_baixado(tmp_path) is False
        baixa.grava_procedencia(tmp_path, fonte, {"completo": True})
        assert baixa.ja_baixado(tmp_path) is True

    def test_falta_de_chave_diz_qual_variavel_falta(self, monkeypatch):
        monkeypatch.delenv(baixa.VAR_CHAVE_ROBOFLOW, raising=False)
        with pytest.raises(RuntimeError, match="ROBOFLOW_API_KEY"):
            baixa._chave_roboflow()

    def test_o_derivado_herda_a_procedencia(self, tmp_path):
        """COCO convertido sem licença ao lado é COCO inutilizável."""
        entrada, saida = tmp_path / "in", tmp_path / "out"
        raiz = entrada / "r1"
        (raiz / "train").mkdir(parents=True)
        (raiz / "train" / "_annotations.coco.json").write_text(
            json.dumps(
                {
                    "images": [{"id": 1, "file_name": "a.jpg", "width": 100, "height": 100}],
                    "annotations": [{"id": 1, "image_id": 1, "category_id": 3, "bbox": [1, 2, 3, 4]}],
                    "categories": [{"id": 3, "name": "gloves"}],
                }
            )
        )
        baixa.grava_procedencia(raiz, baixa.ROBOFLOW[0], {"completo": True})
        assert conv.modo_converter(entrada, saida, "a", gravar=True) == 0
        assert json.loads((saida / "r1" / "PROCEDENCIA.json").read_text())["licenca"] == "CC BY 4.0"
        assert (saida / "r1" / "ATRIBUICAO.txt").exists()
        assert (saida / "r1" / "RELATORIO_CONVERSAO.txt").exists()
        doc = json.loads((saida / "r1" / "_annotations.coco.json").read_text())
        assert [c["name"] for c in doc["categories"] if c["id"]] == conv.classes_da_variante("a")
        assert len(doc["annotations"]) == 1


# ── 6. leitura dos formatos baixados ─────────────────────────────────────────
class TestLeitura:
    def test_le_coco_resolve_nome_da_classe_e_nao_colide_ids_entre_splits(self, tmp_path):
        for split, cat in (("train", "gloves"), ("valid", "no glove")):
            d = tmp_path / split
            d.mkdir()
            (d / "_annotations.coco.json").write_text(
                json.dumps(
                    {
                        "images": [{"id": 1, "file_name": "x.jpg"}],
                        "annotations": [
                            {"id": 1, "image_id": 1, "category_id": 7, "bbox": [0, 0, 5, 5]}
                        ],
                        "categories": [{"id": 7, "name": cat}],
                    }
                )
            )
        anotacoes, imagens = conv.le_coco(tmp_path)
        assert sorted(a["class_name"] for a in anotacoes) == ["gloves", "no glove"]
        assert len({i["id"] for i in imagens}) == 2, "image_id de splits diferentes não pode colidir"
        assert {a["image_id"] for a in anotacoes} == {i["id"] for i in imagens}

    def test_le_oid_normaliza_para_xywh(self, tmp_path):
        with (tmp_path / "validation-3classes.csv").open("w", newline="") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=["ImageID", "Split", "LabelName", "ClassName", "XMin", "XMax", "YMin", "YMax"],
            )
            w.writeheader()
            w.writerow(
                {
                    "ImageID": "abc", "Split": "validation", "LabelName": "/m/0k65p",
                    "ClassName": "Human hand", "XMin": "0.25", "XMax": "0.75",
                    "YMin": "0.10", "YMax": "0.40",
                }
            )
        anotacoes, imagens = conv.le_oid(tmp_path)
        assert anotacoes[0]["class_name"] == "Human hand"
        assert anotacoes[0]["bbox"] == pytest.approx([0.25, 0.10, 0.50, 0.30])
        assert imagens[0]["file_name"] == "images/validation/abc.jpg"

    def test_os_mids_do_open_images_sao_os_conferidos(self):
        """Conferidos em oidv7-class-descriptions-boxable.csv (2026-09-02)."""
        assert baixa.OID_CLASSES == {
            "/m/0k65p": "Human hand",
            "/m/0dzct": "Human face",
            "/m/039xj_": "Human ear",
        }
        assert set(baixa.OID_CLASSES.values()) == set(conv.MAPA["oid"])
