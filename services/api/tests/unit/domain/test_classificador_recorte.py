"""O classificador de recorte só alerta o que a régua autorizou.

Caminho 2 da ADR-0067. As três condições, sempre juntas:

  1. veredito `sem`;
  2. confiança ≥ limiar da família;
  3. classe que PASSOU a régua no campo virgem.

A terceira é a que este arquivo protege com mais cuidado: **a medida viaja no
artefato**. Não é configuração que alguém possa esquecer de ligar — o
`regua.json` vem junto das cabeças, e uma classe que não passou não emite
violação nem que a confiança seja 1,0.

Régua real medida em 25/08 (campo virgem, sem quase-duplicatas):
    luvas/sem 96% (n=27) · mascara/sem 100% (n=16) · oculos/com 91% (n=11) ·
    oculos/sem 90% (n=10)
Detector no MESMO campo: Sem Luvas 25% (n=4), Sem mascara 0% (n=6).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.domain.detectors import classificador_recorte as mod

_TENANT = "63c219d8-fbef-4f3c-a7c9-058c742482e2"

#: régua como o artefato real a carrega
_REGUA = {
    "luvas/sem": {"passa": True, "precisao": 0.96, "n_previsto": 27},
    "luvas/com": {"passa": False, "n_previsto": 5},
    "mascara/sem": {"passa": True, "precisao": 1.0, "n_previsto": 16},
    "mascara/incorreto": {"passa": False, "n_previsto": 2},
    "oculos/sem": {"passa": True, "precisao": 0.90, "n_previsto": 10},
}


def _clf(regua=None, familias=("luvas", "mascara")):
    c = mod.ClassificadorRecorte.__new__(mod.ClassificadorRecorte)
    c.tenant_id = _TENANT
    c.versao = "v1"
    c._regua = _REGUA if regua is None else regua
    c._cabecas = {f: {"cabeca": MagicMock(), "classes": ["com", "sem"]} for f in familias}
    c._backbone = MagicMock()
    c.pronto = True
    c.ultimo_erro = None
    return c


def _julga(c, familia, classe, confianca):
    """Roda `julgar` com a saída da cabeça forçada."""
    torch = pytest.importorskip("torch")
    c._cabecas = {familia: c._cabecas.get(familia) or
                  {"cabeca": MagicMock(), "classes": ["com", "sem"]}}
    idx = c._cabecas[familia]["classes"].index(classe)
    outro = 1 - idx
    logits = torch.full((1, 2), -20.0)
    # softmax de [a, b] com a-b grande o bastante para dar a confiança pedida
    import math
    delta = math.log(confianca / (1 - confianca)) if confianca < 1 else 40.0
    logits[0, idx] = delta / 2
    logits[0, outro] = -delta / 2
    c._cabecas[familia]["cabeca"].return_value = logits
    c._backbone.return_value = torch.zeros(1, 384)
    imagem = _jpeg()
    return c.julgar(imagem)[familia]


def _jpeg() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 128), (120, 120, 120)).save(buf, "JPEG")
    return buf.getvalue()


class TestAReguaAutorizaOAlerta:
    def test_classe_que_passou_pode_alertar(self):
        v = _julga(_clf(), "mascara", "sem", 0.99)
        assert v["veredito"] == "sem"
        assert v["pode_alertar"] is True

    def test_classe_que_NAO_passou_vira_abstencao(self):
        """Mesmo com confiança altíssima: a régua manda."""
        regua = dict(_REGUA, **{"luvas/sem": {"passa": False, "n_previsto": 4}})
        v = _julga(_clf(regua=regua), "luvas", "sem", 0.999)
        assert v["pode_alertar"] is False
        assert v["veredito"] == "nao_visivel"
        assert "não passou a régua" in v["motivo"]

    def test_classe_ausente_da_regua_tambem_abstem(self):
        """Régua sem entrada = não autorizada. Fail closed."""
        v = _julga(_clf(regua={}), "mascara", "sem", 0.99)
        assert v["pode_alertar"] is False


class TestAbstencaoPorConfianca:
    def test_abaixo_do_limiar_e_abstencao(self):
        v = _julga(_clf(), "mascara", "sem", 0.80)
        assert v["veredito"] == "nao_visivel"
        assert v["pode_alertar"] is False
        assert "limiar" in v["motivo"]

    def test_o_limiar_e_o_MESMO_em_que_a_regua_foi_medida(self):
        """Usar outro limiar invalidaria a medida que autoriza a classe."""
        assert mod.LIMIAR_PADRAO == 0.90


class TestPresencaNuncaAlerta:
    def test_veredito_com_e_conformidade(self):
        v = _julga(_clf(), "mascara", "com", 0.99)
        assert v["veredito"] == "com"
        assert v["pode_alertar"] is False
        assert "não é ausência" in v["motivo"]


class TestNaoCarregouEhAbstencaoNaoSilencio:
    def test_classificador_nao_pronto_devolve_vazio(self):
        c = _clf()
        c.pronto = False
        assert c.julgar(_jpeg()) == {}

    def test_singleton_devolve_None_quando_nao_carrega(self):
        mod._cache.clear()
        with patch.object(mod.ClassificadorRecorte, "carregar", return_value=False):
            assert mod.classificador_do_tenant("t-qualquer") is None


class TestOPesoEhVerificado:
    def test_hash_pinado_bate_com_a_tabela_de_licencas(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[5]
        doc = (raiz / "docs" / "WEIGHTS_LICENSES.md").read_text(encoding="utf-8")
        assert mod.PESO_SHA256 in doc, (
            "o sha256 do código tem de ser o mesmo da tabela de licenças, "
            "senão 'Apache 2.0' vale para um arquivo que não é o que roda"
        )

    def test_r2_vem_antes_da_origem_externa(self):
        """Runtime não pode depender de site de terceiro estar de pé."""
        from pathlib import Path

        codigo = Path(mod.__file__).read_text(encoding="utf-8")
        corpo = codigo.split("def _baixa_backbone")[1]
        assert corpo.index("PESO_R2") < corpo.index("PESO_URL")
