"""
Recognition — localização de arquivos do repositório em runtime.

Os executores GPU (training/propagate_seeded.py, training/vast/
remote_train.py) são lidos do DISCO e embutidos no onstart do pod. O
caminho relativo ao repo muda entre ambientes: no checkout local o repo
root fica 6 níveis acima deste pacote; na imagem do worker
(services/api/Dockerfile.worker) `services/api/` vira `/app` e `training/`
é copiado para `/app/training` — `parents[6]` estourava IndexError("6") e
o job morria com o motivo ilegível "6" (visto em e2e no DEV).

`find_repo_file` sobe os parents até achar o arquivo — funciona nos dois
layouts e, quando não acha, falha com mensagem LEGÍVEL (vira
error_reason do job).
"""
from __future__ import annotations

from pathlib import Path


def find_repo_file(*relative: str) -> Path:
    """Primeiro ancestral de ESTE arquivo que contém `relative`. Levanta
    FileNotFoundError com mensagem legível se nenhum contém."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent.joinpath(*relative)
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"{'/'.join(relative)} não encontrado em nenhum ancestral de {here} — "
        "a imagem do worker precisa copiar o diretório training/ "
        "(services/api/Dockerfile.worker)"
    )
