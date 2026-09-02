#!/usr/bin/env python3
"""marcar_gabarito.py — dá emprego permanente a um lote de quadros.

    gabarito (dataset_role='holdout')  mede modelo, NUNCA entra em treino
    pool     (dataset_role='pool')     alimenta treino — o padrão de todos

Por que existe: o A/B das variantes saiu NÃO CONCLUSIVO porque o holdout não
tem caixa das classes de ausência. A correção é anotar à mão ~150 dos 440
quadros cheios colhidos do gravador — e essa correção só vale enquanto esses
quadros nunca treinarem. A trava está no export (versioning_v2.
_snapshot_labeled_frames, migration 133); este script é o único caminho
previsto para ACIONÁ-LA.

⛔ ESTE SCRIPT NÃO ESCOLHE NADA. Ele recebe a lista pronta (a seleção dos
~150 é decisão de quem monta a prova) e marca. Escolher e marcar no mesmo
lugar esconderia o critério dentro de um efeito colateral.

Entrada: um id por linha (UUID), '#' comenta, linha vazia ignorada; use '-'
para ler do stdin. Aceita também JSON (lista de ids, ou lista/objeto com
"frame_id"/"id") e CSV com coluna `frame_id` — que é o formato REAL da fila
(docs/quality/evidence/gabarito-v2/fila-gabarito-150.csv, produzida por
fila_gabarito_v2.py). Ler o CSV aqui evita o `cut -d, -f1` que, esquecido,
manda o cabeçalho para o banco.

IDEMPOTENTE: rodar duas vezes não remarca nem move `dataset_role_set_at`
(FrameRepository.set_dataset_role só toca linha cujo papel difere) — a data
em que o quadro virou gabarito é prova de que ele não estava no treino
anterior, e reescrevê-la apagaria justamente isso.

USO
    export DATABASE_URL=...           # nunca imprima a URL
    python scripts/ops/marcar_gabarito.py --tenant <uuid> --ids gabarito.txt
    python scripts/ops/marcar_gabarito.py --tenant <uuid> --ids - --dry-run
    python scripts/ops/marcar_gabarito.py --tenant <uuid> --ids x.txt --papel pool

--dry-run mostra o que mudaria (contagem por papel atual) sem escrever.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import pathlib
import sys
from uuid import UUID

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "services" / "api"))

logger = logging.getLogger("marcar_gabarito")


def ler_ids(origem: str) -> list[str]:
    """Ids do arquivo (ou stdin com '-'), texto ou JSON. Valida cada UUID.

    Validar aqui e não no banco: um id torto no meio de 150 faria o UPDATE
    inteiro abortar por erro de tipo, e o operador ficaria sem saber qual
    linha do arquivo estava errada.
    """
    bruto = sys.stdin.read() if origem == "-" else pathlib.Path(origem).read_text()
    texto = bruto.strip()
    if texto.splitlines()[:1] and "frame_id" in texto.splitlines()[0] and "," in texto.splitlines()[0]:
        cruas = [linha["frame_id"] for linha in csv.DictReader(io.StringIO(texto))]
    elif texto.startswith(("[", "{")):
        dados = json.loads(texto)
        if isinstance(dados, dict):
            dados = dados.get("frames") or dados.get("frame_ids") or []
        cruas = [
            item if isinstance(item, str) else (item.get("frame_id") or item.get("id"))
            for item in dados
        ]
    else:
        cruas = [
            linha.split("#")[0].strip()
            for linha in texto.splitlines()
        ]

    ids: list[str] = []
    for pos, valor in enumerate(cruas, start=1):
        if not valor:
            continue
        try:
            ids.append(str(UUID(str(valor))))
        except (ValueError, AttributeError):
            raise SystemExit(f"item {pos} não é UUID: {valor!r}") from None
    if not ids:
        raise SystemExit("nenhum id na entrada")
    return ids


def _repo(dsn: str):
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.frame_repository import (
        FrameRepository,
    )

    DatabasePool.initialize(dsn, 1, 2)
    return FrameRepository(DatabasePool.get_instance())


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--tenant", required=True, help="tenant_id (escopo obrigatório)")
    p.add_argument("--ids", required=True, help="arquivo com os ids, ou '-' para stdin")
    p.add_argument("--papel", choices=("holdout", "pool"), default="holdout")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    dsn = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not dsn:
        logger.error("DATABASE_URL/DATABASE_PUBLIC_URL ausente no ambiente")
        return 1

    ids = ler_ids(args.ids)
    repo = _repo(dsn)

    # Estado ANTES — é o que torna o resultado auditável: sem ele, "marcados: 0"
    # tanto pode significar "já estava tudo certo" quanto "nenhum id existe".
    atual = repo._execute(
        "SELECT dataset_role, COUNT(*) AS n FROM training_frames "
        "WHERE id = ANY(%s::uuid[]) AND tenant_id = %s GROUP BY dataset_role",
        (ids, args.tenant),
    )
    encontrados = sum(int(r["n"]) for r in atual)
    logger.info(
        "entrada: %d id(s) | no tenant: %d | por papel atual: %s | alvo: %s",
        len(ids), encontrados,
        {r["dataset_role"]: int(r["n"]) for r in atual} or "{}",
        args.papel,
    )
    if encontrados != len(set(ids)):
        logger.warning(
            "%d id(s) não existem neste tenant e serão ignorados (C-01: id de "
            "outro tenant não casa o WHERE e não vaza existência)",
            len(set(ids)) - encontrados,
        )

    if args.dry_run:
        logger.info("--dry-run: nada escrito")
        return 0

    r = repo.set_dataset_role(ids, args.papel, args.tenant)
    logger.info(
        "papel '%s' aplicado: marcados=%d ja_no_papel=%d nao_encontrados=%d",
        args.papel, r["marcados"], r["ja_no_papel"], r["nao_encontrados"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
