"""`list_keys` acima de 1000 objetos — o truncamento que matou um treino.

`list_objects_v2` devolve no máximo 1000 chaves por resposta. A versão anterior
lia só a primeira página: acima disso ela mentia por OMISSÃO, sem erro.

Custo real (2026-08-20): o split `train` do v8 tem 1293 imagens. O dispatch
empacotou 1000, o pod baixou um zip com 293 a menos, e o treino morreu na época
0 com `FileNotFoundError` — depois de provisionar GPU e cobrar. O pré-flight
aprovou porque contava as MESMAS chaves truncadas.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.infrastructure.storage.r2_storage import R2Storage


def _storage_com_paginas(paginas: list[list[str]]) -> R2Storage:
    storage = R2Storage.__new__(R2Storage)
    storage._bucket = "bucket-teste"  # noqa: SLF001
    cliente = MagicMock()
    paginador = MagicMock()
    paginador.paginate.return_value = [
        {"Contents": [{"Key": k} for k in pagina]} for pagina in paginas
    ]
    cliente.get_paginator.return_value = paginador
    storage._client = cliente  # noqa: SLF001
    return storage


def test_1293_chaves_em_duas_paginas_voltam_INTEIRAS() -> None:
    """O caso exato do v8: 1293 imagens, R2 devolve 1000 + 293."""
    pagina1 = [f"train/img-{i:05d}.jpg" for i in range(1000)]
    pagina2 = [f"train/img-{i:05d}.jpg" for i in range(1000, 1293)]

    chaves = _storage_com_paginas([pagina1, pagina2]).list_keys("train/")

    assert len(chaves) == 1293, "truncou — é o defeito que matou o treino"
    assert chaves[-1] == "train/img-01292.jpg"


def test_pagina_unica_continua_funcionando() -> None:
    chaves = _storage_com_paginas([[f"val/{i}.jpg" for i in range(303)]]).list_keys("val/")
    assert len(chaves) == 303


def test_prefixo_vazio_devolve_lista_vazia() -> None:
    assert _storage_com_paginas([[]]).list_keys("nada/") == []


def test_usa_PAGINADOR_e_nao_chamada_unica() -> None:
    """Fixa o mecanismo: `list_objects_v2` direto volta a truncar em 1000."""
    storage = _storage_com_paginas([["a"]])
    storage.list_keys("x/")
    storage._client.get_paginator.assert_called_once_with("list_objects_v2")  # noqa: SLF001
    storage._client.list_objects_v2.assert_not_called()  # noqa: SLF001
