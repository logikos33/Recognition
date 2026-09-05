"""Vínculo recorte → frame de origem: validação na entrada e reprojeção na saída.

POR QUE ISTO EXISTE
O modelo é SERVIDO em frame cheio de CFTV (single-stage: o engine chama
`predict(frame)` com o quadro inteiro e o detector redimensiona o quadro
inteiro — não há recorte de pessoa em nenhum ponto do caminho servido). Mas
95,9% do dado de TREINO é recorte de pessoa, produzido no edge por
`person_detector.crop_person`. Treina-se num domínio e serve-se noutro.

Até a migration 132 o coletor recortava sem gravar de onde o recorte saiu, e a
r2_key não desempatava (recorte e frame cheio no mesmo prefixo, nome UUID
aleatório). Os 5.259 recortes anotados do RVB continuam irreprojetáveis — isso
não tem conserto retroativo. Daqui pra frente `training_frames.crop_origin`
carrega a geometria, e `reproject_annotation` é o que a transforma numa
anotação em coordenadas do frame cheio.

FORMATO (o mesmo que `PersonCrop.origin` produz no edge):
    {"box": [x, y, w, h], "source_size": [W, H]}   — pixels do frame ORIGINAL
"""
from __future__ import annotations

import json
from typing import Any

#: Teto do campo de form. Um vínculo válido tem ~60 bytes; qualquer coisa
#: perto disto já é payload inventado, e é mais barato recusar antes de
#: chamar o parser de JSON do que depois.
_MAX_RAW_BYTES = 512


def parse_crop_origin(raw: str | None) -> dict[str, Any] | None:
    """Valida o campo vindo do device e devolve um dict LIMPO (ou None).

    O device é autenticado (RS256, ADR-0019), mas isso autentica quem fala, não
    o que fala: o valor vai direto pra uma coluna jsonb e daí pra uma conta de
    coordenadas. Então valida-se de verdade e monta-se um dict novo com as duas
    chaves conhecidas — nada do que o device mandar a mais é persistido.

    Ausente/vazio -> None (frame cheio, upload manual: não há recorte).
    Inválido -> ValueError, que a rota converte em 422. Recusar é melhor que
    gravar uma caixa impossível: um vínculo errado mente pior que um ausente,
    porque parece existir.
    """
    if raw is None or not raw.strip():
        return None
    if len(raw.encode("utf-8")) > _MAX_RAW_BYTES:
        raise ValueError("crop_origin grande demais")
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("crop_origin não é JSON válido") from exc
    if not isinstance(parsed, dict):
        raise ValueError("crop_origin deve ser um objeto JSON")

    box = _ints(parsed.get("box"), 4, "box")
    source = _ints(parsed.get("source_size"), 2, "source_size")
    x, y, w, h = box
    sw, sh = source
    if sw <= 0 or sh <= 0:
        raise ValueError("source_size deve ser positivo")
    if w <= 0 or h <= 0:
        raise ValueError("box precisa ter largura e altura positivas")
    if x < 0 or y < 0 or x + w > sw or y + h > sh:
        raise ValueError("box precisa caber dentro de source_size")
    return {"box": [x, y, w, h], "source_size": [sw, sh]}


def _ints(value: Any, size: int, field: str) -> list[int]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{field} deve ser uma lista de {size} inteiros")
    out = []
    for item in value:
        # bool é subclasse de int em Python — True viraria 1 em silêncio.
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"{field} deve conter inteiros")
        out.append(item)
    return out


def reproject_annotation(
    annotation: dict[str, Any], origin: dict[str, Any]
) -> dict[str, float]:
    """Anotação normalizada no RECORTE -> normalizada no FRAME ORIGINAL.

    Entrada e saída no formato de `frame_annotations` (YOLO: x_center, y_center,
    width, height, todos 0..1) — a entrada relativa ao recorte, a saída relativa
    ao quadro cheio.

    A conta, em pixels do original:
        centro_x = box_x + x_center * box_w      # tira do recorte, soma o offset
        centro_y = box_y + y_center * box_h
    e volta a normalizar dividindo pelo tamanho do original. As dimensões
    escalam sem offset: uma caixa que ocupa metade de um recorte de 600px de
    largura ocupa 300/1920 do frame de 1920.

    Não clampa em 0..1: por construção o resultado já cabe (a caixa está dentro
    do recorte, que está dentro do frame — `parse_crop_origin` garante o
    segundo). Clampar aqui esconderia entrada inconsistente em vez de deixá-la
    aparecer no CHECK da tabela.
    """
    x, y, w, h = origin["box"]
    sw, sh = origin["source_size"]
    return {
        "x_center": (x + annotation["x_center"] * w) / sw,
        "y_center": (y + annotation["y_center"] * h) / sh,
        "width": annotation["width"] * w / sw,
        "height": annotation["height"] * h / sh,
    }
