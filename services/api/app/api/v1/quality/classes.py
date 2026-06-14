"""
Módulo de Qualidade — Classes YOLO e categorias de defeito.

Classes usadas no modelo de inspeção de qualidade industrial.
Cada classe tem id, name (slug YOLO), color (hex), label (PT-BR) e category.
"""

# Classes YOLO do módulo de qualidade
# category "ok" → produto aceito; category "nok" → produto rejeitado
QUALITY_CLASSES = [
    {
        "id": 0,
        "name": "produto_ok",
        "color": "#43D186",
        "label": "Produto OK",
        "category": "ok",
    },
    {
        "id": 1,
        "name": "produto_nok",
        "color": "#EF5350",
        "label": "Produto NOK",
        "category": "nok",
    },
    {
        "id": 2,
        "name": "defeito_visual",
        "color": "#FF8A65",
        "label": "Defeito Visual (risco/arranhão)",
        "category": "nok",
    },
    {
        "id": 3,
        "name": "defeito_dimensional",
        "color": "#FFB74D",
        "label": "Defeito Dimensional",
        "category": "nok",
    },
    {
        "id": 4,
        "name": "defeito_superficie",
        "color": "#F06292",
        "label": "Defeito de Superfície",
        "category": "nok",
    },
    {
        "id": 5,
        "name": "defeito_bolha",
        "color": "#CE93D8",
        "label": "Bolha / Inclusão de Ar",
        "category": "nok",
    },
    {
        "id": 6,
        "name": "defeito_mancha",
        "color": "#4FC3F7",
        "label": "Mancha / Contaminação",
        "category": "nok",
    },
    {
        "id": 7,
        "name": "montagem_faltando",
        "color": "#E57373",
        "label": "Componente Faltando",
        "category": "nok",
    },
    {
        "id": 8,
        "name": "montagem_errada",
        "color": "#FFD54F",
        "label": "Montagem Incorreta",
        "category": "nok",
    },
]

# Mapeamento slug → label PT-BR para categorias de defeito
DEFECT_CATEGORIES = {
    "visual": "Visual (risco/arranhão/mancha)",
    "dimensional": "Dimensional (fora de tolerância)",
    "superficie": "Superfície (bolha/poro/trinca)",
    "montagem": "Montagem (faltando/errado)",
    "outro": "Outro",
}

# Slugs válidos para validação nos endpoints
VALID_DEFECT_CATEGORIES = list(DEFECT_CATEGORIES.keys())

# IDs de classe válidos para validação de anotações
VALID_CLASS_IDS = [c["id"] for c in QUALITY_CLASSES]
