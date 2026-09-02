"""Unit — vínculo recorte→frame de origem (migration 132).

O caso da reprojeção é MONTADO À MÃO com números redondos, para que a resposta
seja conferível de cabeça e o teste reprove uma conta errada (offset esquecido,
x trocado com y) em vez de ecoar o que o código faz.
"""
import pytest

from app.domain.services.crop_origin import parse_crop_origin, reproject_annotation

# Frame de 1000x500. Recorte de 200x100 começando em (300, 100).
_ORIGIN = {"box": [300, 100, 200, 100], "source_size": [1000, 500]}


class TestReprojecao:
    def test_centro_do_recorte_cai_no_centro_do_recorte_dentro_do_frame(self):
        """Conta à mão: o centro do recorte está em (300+100, 100+50) = (400,150)
        px do original; normalizado, 400/1000 = 0.4 e 150/500 = 0.3. Uma caixa
        que ocupa metade do recorte mede 100/1000 = 0.1 por 50/500 = 0.1."""
        anotacao = {"x_center": 0.5, "y_center": 0.5, "width": 0.5, "height": 0.5}

        r = reproject_annotation(anotacao, _ORIGIN)

        assert r == pytest.approx(
            {"x_center": 0.4, "y_center": 0.3, "width": 0.1, "height": 0.1}
        )

    def test_canto_superior_esquerdo_do_recorte_e_o_offset(self):
        """Anotação colada no canto (0,0) do recorte tem de virar exatamente o
        offset do recorte: 300/1000 = 0.3 e 100/500 = 0.2. É este caso que
        reprova quem esquecer de somar o offset."""
        anotacao = {"x_center": 0.0, "y_center": 0.0, "width": 0.1, "height": 0.1}

        r = reproject_annotation(anotacao, _ORIGIN)

        assert r["x_center"] == pytest.approx(0.3)
        assert r["y_center"] == pytest.approx(0.2)

    def test_x_e_y_nao_sao_intercambiaveis(self):
        """Caixa assimétrica num recorte assimétrico: trocar x com y (ou w com
        h) dá números diferentes, então o teste pega a troca."""
        anotacao = {"x_center": 0.25, "y_center": 0.75, "width": 0.4, "height": 0.2}

        r = reproject_annotation(anotacao, _ORIGIN)

        # x: (300 + 0.25*200)/1000 = 350/1000       y: (100 + 0.75*100)/500 = 175/500
        assert r["x_center"] == pytest.approx(0.35)
        assert r["y_center"] == pytest.approx(0.35)  # coincidem, mas...
        # ...largura e altura não: 0.4*200/1000 = 0.08 vs 0.2*100/500 = 0.04
        assert r["width"] == pytest.approx(0.08)
        assert r["height"] == pytest.approx(0.04)

    def test_recorte_que_e_o_frame_inteiro_e_identidade(self):
        origem = {"box": [0, 0, 640, 480], "source_size": [640, 480]}
        anotacao = {"x_center": 0.3, "y_center": 0.7, "width": 0.2, "height": 0.4}

        assert reproject_annotation(anotacao, origem) == pytest.approx(anotacao)

    def test_resultado_continua_dentro_do_frame(self):
        """Caixa que ocupa o recorte INTEIRO não pode escapar de 0..1 — é o
        CHECK de frame_annotations (x_center BETWEEN 0 AND 1)."""
        anotacao = {"x_center": 0.5, "y_center": 0.5, "width": 1.0, "height": 1.0}

        r = reproject_annotation(anotacao, _ORIGIN)

        assert all(0.0 <= v <= 1.0 for v in r.values())


class TestParseCropOrigin:
    def test_ausente_vira_none(self):
        assert parse_crop_origin(None) is None
        assert parse_crop_origin("") is None
        assert parse_crop_origin("   ") is None

    def test_valido_devolve_dict_limpo(self):
        assert parse_crop_origin(
            '{"box": [300, 100, 200, 100], "source_size": [1000, 500]}'
        ) == _ORIGIN

    def test_chave_desconhecida_nao_e_persistida(self):
        """O device é autenticado, o que ele diz não é — só as duas chaves
        conhecidas entram na coluna jsonb."""
        r = parse_crop_origin(
            '{"box": [0,0,10,10], "source_size": [10,10], "lixo": {"a": 1}}'
        )
        assert r == {"box": [0, 0, 10, 10], "source_size": [10, 10]}

    @pytest.mark.parametrize(
        "raw",
        [
            "não é json",
            "[1,2,3]",                                          # não é objeto
            '{"box": [1,2,3], "source_size": [10,10]}',          # box curta
            '{"box": [1,2,3,4]}',                                # sem source_size
            '{"box": [0,0,"10",10], "source_size": [10,10]}',    # string no lugar de int
            '{"box": [0,0,10.5,10], "source_size": [10,10]}',    # float não é px
            '{"box": [0,0,true,10], "source_size": [10,10]}',    # bool é subclasse de int
            '{"box": [0,0,0,10], "source_size": [10,10]}',       # largura zero
            '{"box": [-1,0,10,10], "source_size": [10,10]}',     # offset negativo
            '{"box": [5,0,10,10], "source_size": [10,10]}',      # estoura a borda
            '{"box": [0,0,10,10], "source_size": [0,10]}',       # frame de largura zero
        ],
    )
    def test_invalido_levanta_value_error(self, raw):
        with pytest.raises(ValueError):
            parse_crop_origin(raw)

    def test_payload_gigante_e_recusado_antes_do_parser(self):
        with pytest.raises(ValueError, match="grande demais"):
            parse_crop_origin('{"box": [0,0,10,10], "lixo": "' + "x" * 600 + '"}')
