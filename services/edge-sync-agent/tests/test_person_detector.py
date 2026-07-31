"""Gatilho de coleta por pessoa — degradação e semântica do resultado.

O que importa aqui NÃO é a acurácia do YOLOX (isso se mede em campo, com
passagens reais — ver o relatório de recall da fase 1), e sim que o coletor
nunca pare de coletar por causa deste detector.
"""

from __future__ import annotations

import builtins

import pytest

from app.collector.person_detector import (
    PersonBox,
    PersonDetector,
    PersonResult,
    build_person_detector_from_env,
)


class TestDegradacao:
    def test_modelo_ausente_nao_fica_pronto(self, tmp_path):
        d = PersonDetector(model_path=str(tmp_path / "nao_existe.onnx"))
        assert d.is_ready is False

    def test_modelo_ausente_devolve_indeterminado(self, tmp_path):
        """`undetermined`, não `found=False`: o coletor precisa distinguir
        'olhei e não tem gente' de 'não consegui olhar'. Confundir os dois
        pararia a coleta silenciosamente."""
        d = PersonDetector(model_path=str(tmp_path / "nao_existe.onnx"))
        r = d.detect(b"\xff\xd8qualquer-coisa")
        assert r.undetermined is True
        assert r.found is False

    def test_sem_onnxruntime_degrada(self, tmp_path, monkeypatch):
        modelo = tmp_path / "fake.onnx"
        modelo.write_bytes(b"nao-e-um-onnx-de-verdade")
        real_import = builtins.__import__

        def sem_ort(name, *args, **kwargs):
            if name == "onnxruntime":
                raise ImportError("sem onnxruntime neste ambiente")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", sem_ort)
        d = PersonDetector(model_path=str(modelo))
        assert d.is_ready is False
        assert d.detect(b"x").undetermined is True

    def test_onnx_invalido_degrada_sem_estourar(self, tmp_path):
        """Arquivo existe mas não é um ONNX válido — carga falha, não explode."""
        modelo = tmp_path / "corrompido.onnx"
        modelo.write_bytes(b"lixo" * 100)
        d = PersonDetector(model_path=str(modelo))
        assert d.is_ready is False

    def test_erro_de_inferencia_vira_indeterminado(self, tmp_path):
        d = PersonDetector(model_path=str(tmp_path / "x.onnx"))

        class SessaoQuebrada:
            def run(self, *_a, **_k):
                raise RuntimeError("falha de inferência")

        d._session = SessaoQuebrada()  # noqa: SLF001
        r = d.detect(b"\xff\xd8")
        assert r.undetermined is True
        assert r.found is False


class TestResultado:
    def test_nao_encontrado_nao_e_indeterminado(self):
        """Distinção que o coletor usa pra decidir entre pular e degradar."""
        r = PersonResult(found=False)
        assert r.undetermined is False

    def test_box_carrega_confianca(self):
        b = PersonBox(x=10, y=20, w=30, h=40, confidence=0.87)
        assert (b.x, b.y, b.w, b.h) == (10, 20, 30, 40)
        assert b.confidence == 0.87


class TestBuilderDeAmbiente:
    def test_desligado_explicitamente_devolve_none(self):
        for valor in ("0", "false", "no", "off", "OFF"):
            assert build_person_detector_from_env({"COLLECTOR_PERSON_TRIGGER": valor}) is None

    def test_ligado_por_padrao(self, tmp_path):
        d = build_person_detector_from_env(
            {"COLLECTOR_PERSON_MODEL_PATH": str(tmp_path / "ausente.onnx")}
        )
        assert isinstance(d, PersonDetector)

    def test_limiar_vem_do_ambiente(self, tmp_path):
        d = build_person_detector_from_env(
            {
                "COLLECTOR_PERSON_MODEL_PATH": str(tmp_path / "ausente.onnx"),
                "COLLECTOR_PERSON_CONFIDENCE": "0.6",
                "COLLECTOR_PERSON_NMS_IOU": "0.3",
            }
        )
        assert d._confidence == pytest.approx(0.6)  # noqa: SLF001
        assert d._nms_iou == pytest.approx(0.3)  # noqa: SLF001


class TestLadrilhamento:
    """2x2 sobreposto: medido em campo, recall 52% -> 90% nos frames da RVB.

    A causa é escala — o substream entrega 704x480 e a entrada do modelo é
    416x416, o que encolhe a pessoa a ~59%; quem está curvado some. Baixar o
    limiar não resolve (0.10 -> 67%).
    """

    def _det(self, tmp_path, **kw):
        return PersonDetector(model_path=str(tmp_path / "ausente.onnx"), **kw)

    def test_padrao_e_2x2(self, tmp_path):
        d = self._det(tmp_path)
        assert (d._tile_nx, d._tile_ny) == (2, 2)  # noqa: SLF001

    def test_1x1_devolve_o_frame_inteiro_sem_offset(self, tmp_path):
        """Construtor ainda aceita (1,1) — quem barra é _parse_tile_grid, pra
        que o caminho de código do frame inteiro siga testável."""
        from PIL import Image

        d = self._det(tmp_path, tile_grid=(1, 1))
        img = Image.new("RGB", (704, 480))
        tiles = d._tiles(img)  # noqa: SLF001
        assert len(tiles) == 1
        assert tiles[0][1:] == (0, 0)

    def test_2x2_gera_quatro_ladrilhos_sobrepostos(self, tmp_path):
        from PIL import Image

        d = self._det(tmp_path, tile_grid=(2, 2))
        tiles = d._tiles(Image.new("RGB", (704, 480)))  # noqa: SLF001
        assert len(tiles) == 4
        largura = tiles[0][0].size[0]
        assert largura > 704 // 2, "sem sobreposição a pessoa some na emenda"

    def test_ladrilho_nunca_sai_do_frame(self, tmp_path):
        from PIL import Image

        d = self._det(tmp_path, tile_grid=(2, 2))
        w, h = 704, 480
        for crop, off_x, off_y in d._tiles(Image.new("RGB", (w, h))):  # noqa: SLF001
            assert off_x >= 0 and off_y >= 0
            assert off_x + crop.size[0] <= w
            assert off_y + crop.size[1] <= h

    def test_grid_invalido_cai_no_padrao(self):
        from app.collector.person_detector import _parse_tile_grid

        for ruim in ("", "abc", "0x2", "2x", "-1x3", "2"):
            assert _parse_tile_grid(ruim) == (2, 2)

    def test_grid_valido_e_respeitado(self):
        from app.collector.person_detector import _parse_tile_grid

        assert _parse_tile_grid("3x2") == (3, 2)
        assert _parse_tile_grid("2X2") == (2, 2)


class TestRecortePessoa:
    """Desfecho C: sobe o recorte da pessoa, não o frame inteiro.

    Medido num frame real da RVB (pessoa 54x282 em 1920x1080): o recorte sai
    com ~10 KB e cabeça de ~40px, contra 157 KB e ~17px do frame do substream.
    """

    def _jpeg(self, w, h):
        import io

        from PIL import Image

        b = io.BytesIO()
        Image.new("RGB", (w, h), (120, 130, 140)).save(b, "JPEG")
        return b.getvalue()

    def test_recorte_e_muito_menor_que_o_frame(self):
        from app.collector.person_detector import crop_person

        frame = self._jpeg(1920, 1080)
        r = crop_person(frame, PersonBox(x=1097, y=105, w=54, h=282, confidence=0.6))
        assert len(r) < len(frame)

    def test_recorte_inclui_margem_ao_redor_da_pessoa(self):
        """Margem existe porque o alvo é EPI de CABEÇA — bbox justo corta
        exatamente o que se quer anotar."""
        import io

        from PIL import Image

        from app.collector.person_detector import crop_person

        caixa = PersonBox(x=800, y=300, w=100, h=280, confidence=0.7)
        r = crop_person(self._jpeg(1920, 1080), caixa)
        w, h = Image.open(io.BytesIO(r)).size
        assert w > caixa.w and h > caixa.h

    def test_recorte_nao_estoura_a_borda_do_frame(self):
        """Pessoa colada na borda: a margem tem que ser aparada, não gerar
        coordenada negativa ou além do frame."""
        import io

        from PIL import Image

        from app.collector.person_detector import crop_person

        frame = self._jpeg(704, 480)
        r = crop_person(frame, PersonBox(x=0, y=0, w=60, h=200, confidence=0.5))
        w, h = Image.open(io.BytesIO(r)).size
        assert 0 < w <= 704 and 0 < h <= 480

    def test_recorte_preserva_resolucao_nativa(self):
        """Nada de reescalar: o ganho todo é ter o pixel original da cabeça."""
        import io

        from PIL import Image

        from app.collector.person_detector import crop_person

        caixa = PersonBox(x=500, y=200, w=100, h=300, confidence=0.8)
        r = crop_person(self._jpeg(1920, 1080), caixa, margin_x=0.0, margin_y=0.0)
        assert Image.open(io.BytesIO(r)).size == (100, 300)


class TestTiles1x1Proibido:
    """1x1 deixou de ser aceito na fase 1c: com captura em 1080p ele não acha
    a pessoa (54px viram 12px na entrada de 416) — seria uma config que desliga
    a coleta em silêncio."""

    def test_1x1_cai_no_padrao(self):
        from app.collector.person_detector import _parse_tile_grid

        assert _parse_tile_grid("1x1") == (2, 2)

    def test_outros_grids_continuam_valendo(self):
        from app.collector.person_detector import _parse_tile_grid

        assert _parse_tile_grid("3x2") == (3, 2)
        assert _parse_tile_grid("2x2") == (2, 2)
