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
    python scripts/ops/marcar_gabarito.py --tenant <uuid> \
        --ids docs/quality/evidence/gabarito-v2/fila-gabarito-150.csv --ordem

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


def ler_ordem(origem: str) -> "dict[str, int]":
    """{frame_id: posicao} do CSV da fila. Só o CSV tem posto — os outros
    formatos (txt/JSON) são listas de ids sem ordem declarada, e inferir a
    ordem da posição da linha seria transformar formatação em decisão.

    A ordem existe porque a fila JÁ foi decidida
    (`fila_gabarito_v2.py` → `fila-gabarito-150.csv`: probabilidade de conter
    ausência real × prioridade de câmera do dono). A tela de triagem apenas
    OBEDECE — reordenar no cliente seria inventar uma segunda fila.
    """
    bruto = sys.stdin.read() if origem == "-" else pathlib.Path(origem).read_text()
    linhas = bruto.strip().splitlines()
    if not linhas or "frame_id" not in linhas[0] or "," not in linhas[0]:
        raise SystemExit("--ordem exige o CSV da fila (com colunas frame_id,posicao)")
    ordem: dict[str, int] = {}
    for linha in csv.DictReader(io.StringIO(bruto.strip())):
        posicao = linha.get("posicao")
        if not posicao:
            raise SystemExit("CSV sem coluna `posicao` — nada a ordenar")
        ordem[str(UUID(linha["frame_id"]))] = int(posicao)
    return ordem


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
    p.add_argument(
        "--ordem",
        action="store_true",
        help="grava também training_frames.priority_rank = posicao do CSV "
        "(a ordem que a tela de triagem obedece)",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    # `--ordem` relê o arquivo para pegar a coluna `posicao`; stdin não se lê
    # duas vezes, e o segundo read voltaria vazio — ordem silenciosamente não
    # gravada é pior que recusa explícita.
    if args.ordem and args.ids == "-":
        p.error("--ordem exige arquivo (o CSV da fila), não stdin")

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

    if args.ordem:
        # `priority_rank` reaproveitada: já existe, tem índice
        # (idx_frames_priority), estava 100% NULL nos quadros do gabarito e
        # não tem NENHUM leitor em Python — e "posto na fila por prioridade" é
        # o que o nome já diz. Coluna nova para o mesmo fato seria migration
        # a mais pelo mesmo dado.
        # Escopo por tenant no WHERE, como todo o resto (C-01).
        ordem = ler_ordem(args.ids)
        tocados = repo._execute_mutation_no_return(
            "UPDATE training_frames tf SET priority_rank = v.posicao "
            "FROM (SELECT unnest(%s::uuid[]) AS id, unnest(%s::int[]) AS posicao) v "
            "WHERE tf.id = v.id AND tf.tenant_id = %s "
            "  AND tf.priority_rank IS DISTINCT FROM v.posicao",
            (list(ordem.keys()), list(ordem.values()), args.tenant),
        )
        logger.info("ordem da fila gravada em priority_rank: %d linha(s)", tocados)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
