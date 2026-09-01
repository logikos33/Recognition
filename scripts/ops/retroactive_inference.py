#!/usr/bin/env python3
"""retroactive_inference.py — dispara `tasks.inference.retroactive_inference`
para um tenant/janela de datas (Nível 1: inferência sobre frames JÁ NA NUVEM,
sem tocar no box).

Por quê: o único caminho de alerta hoje é `inference_loop`, que exige stream
RTSP AO VIVO — sem stream ativo, zero alerta, mesmo com frames chegando via
NVR todo dia (`training_frames.source='nvr'`). Este script dispara a task que
fecha esse buraco: reusa o MESMO detector/regra/escrita do caminho ao vivo,
só que sobre frames já armazenados.

Dry-run por padrão (mesmo padrão dos outros scripts desta pasta — ver
`aplicar_calibracao_rvb.py`): sem `--aplicar`, só CONTA quantos frames
`source='nvr'` entrariam na janela e sai, sem tocar em nada. Com `--aplicar`,
exige `CONFIRM_OPS=1` (hard gate, mesmo padrão de `import_nvr_channels_rvb.py`)
e enfileira a task — quem processa é o WORKER, não este script; a
contagem de alertas criados sai nos logs do worker, não aqui.

Uso:
    DATABASE_URL=... python3 scripts/ops/retroactive_inference.py \\
        --tenant-slug rvb --date-from 2026-09-01 --date-to 2026-09-02
    # mostra quantos frames entrariam na janela — não dispara nada

    DATABASE_URL=... REDIS_URL=... CONFIRM_OPS=1 \\
        python3 scripts/ops/retroactive_inference.py \\
        --tenant-slug rvb --date-from 2026-09-01 --date-to 2026-09-02 --aplicar
    # enfileira a task na fila 'inference'

Variáveis de ambiente:
    DATABASE_URL   PostgreSQL connection string (obrigatório)
    REDIS_URL      broker do Celery (obrigatório só com --aplicar)
    CONFIRM_OPS    precisa ser exatamente "1" — hard gate para --aplicar
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant-slug", default="rvb")
    ap.add_argument("--date-from", required=True, help="YYYY-MM-DD (UTC, inclusive)")
    ap.add_argument("--date-to", required=True, help="YYYY-MM-DD (UTC, exclusive)")
    ap.add_argument("--module-code", default="epi")
    ap.add_argument(
        "--aplicar", action="store_true",
        help="sem isto, só mostra quantos frames entrariam na janela",
    )
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        return 2

    try:
        date_from = datetime.fromisoformat(args.date_from)
        date_to = datetime.fromisoformat(args.date_to)
    except ValueError:
        print("--date-from/--date-to precisam ser YYYY-MM-DD.", file=sys.stderr)
        return 2
    if date_to <= date_from:
        print("--date-to precisa ser depois de --date-from.", file=sys.stderr)
        return 2

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM public.tenants WHERE slug = %s", (args.tenant_slug,)
            )
            row = cur.fetchone()
            if not row:
                print(f"tenant '{args.tenant_slug}' não existe neste banco.", file=sys.stderr)
                return 1
            tenant_id = str(row["id"])

            cur.execute(
                "SELECT COUNT(*) AS n FROM training_frames "
                " WHERE tenant_id = %s AND source = 'nvr' AND module_code = %s "
                "   AND camera_id IS NOT NULL AND captured_at IS NOT NULL "
                "   AND captured_at >= %s AND captured_at < %s",
                (tenant_id, args.module_code, date_from, date_to),
            )
            n_elegiveis = cur.fetchone()["n"]
    finally:
        conn.close()

    print(f"tenant {args.tenant_slug} ({tenant_id})  módulo {args.module_code}")
    print(f"janela [{date_from.isoformat()} .. {date_to.isoformat()})  "
          f"frames source=nvr elegíveis: {n_elegiveis}")

    if n_elegiveis == 0:
        print("Nada a fazer.")
        return 0

    if not args.aplicar:
        print("\nDRY-RUN — nenhuma task disparada. Rode de novo com --aplicar "
              "(e CONFIRM_OPS=1) para enfileirar.")
        return 0

    if os.environ.get("CONFIRM_OPS") != "1":
        print(
            "\nRECUSADO: --aplicar exige CONFIRM_OPS=1 explícito.",
            file=sys.stderr,
        )
        return 2

    # A task mora em services/api/app — este script roda da raiz do repo.
    api_dir = str(Path(__file__).resolve().parents[2] / "services" / "api")
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)

    from app.infrastructure.queue.tasks.inference import (  # noqa: PLC0415
        retroactive_inference,
    )

    result = retroactive_inference.delay(
        tenant_id=tenant_id,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        module_code=args.module_code,
    )
    print(f"\nTask enfileirada: {result.id} (fila 'inference').")
    print("Acompanhe pelos logs do worker (retroactive_inference_start / "
          "retroactive_inference_done) — este script não espera o resultado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
