"""Prova que a matriz de cobertura conta IGUAL ao export de treino.

"Tela que conta diferente do export mente." Este script roda contra um banco
real (DEV) e compara, com número:
  - caminho EXPORT  = SQL de versioning_v2._fetch_annotations + o pós-filtro de
    procedência que a função aplica em Python (source='manual' OR reviewed_by).
  - caminho MATRIZ  = COUNT sobre o fragmento _COVERAGE_UNIVERSE do
    AnnotationRepository (que já embute a procedência em SQL).

Os DOIS SQLs são EXTRAÍDOS do código-fonte em tempo de execução — não copiados
aqui — então drift em qualquer um dos lados quebra a comparação. Sem importar o
app (evita puxar Flask/Celery); só psycopg2.

Uso (via railway, que injeta a URL — nunca imprima a URL):
  railway run --service Postgres bash -c \\
    'python scripts/ops/verify_coverage_matches_export.py <tenant_id> [module]'
"""
import os
import pathlib
import re
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO_PY = ROOT / "services/api/app/infrastructure/database/repositories/annotation_repository.py"
EXPORT_PY = ROOT / "services/api/app/infrastructure/queue/tasks/versioning_v2.py"


def _extract_universe() -> str:
    src = REPO_PY.read_text(encoding="utf-8")
    m = re.search(r'_COVERAGE_UNIVERSE\s*=\s*"""(.*?)"""', src, re.DOTALL)
    if not m:
        sys.exit("não achei _COVERAGE_UNIVERSE em annotation_repository.py")
    return m.group(1)


def _extract_export_sql() -> str:
    src = EXPORT_PY.read_text(encoding="utf-8")
    start = src.index("def _fetch_annotations")
    span = src[start:src.index("\ndef ", start + 1)]
    m = re.search(r'_execute\(\s*"""(.*?)"""', span, re.DOTALL)
    if not m:
        sys.exit("não achei o SQL de _fetch_annotations em versioning_v2.py")
    return m.group(1)


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("uso: verify_coverage_matches_export.py <tenant_id> [module]")
    tenant, module = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "epi")
    dsn = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_PUBLIC_URL/DATABASE_URL ausente no ambiente")

    export_sql = _extract_export_sql()
    universe = _extract_universe()
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        # EXPORT: roda o SQL da função + o pós-filtro de procedência (Python).
        cur.execute(export_sql, (tenant, module))
        rows = cur.fetchall()
        export_rows = [
            r for r in rows
            if r.get("source", "manual") == "manual" or r.get("reviewed_by") is not None
        ]
        export_boxes = len(export_rows)
        export_images = len({r["frame_id"] for r in export_rows})
        # MATRIZ: COUNT sobre o mesmo universo embutido em SQL.
        cur.execute(
            "SELECT COUNT(*) AS boxes, COUNT(DISTINCT a.frame_id) AS images "
            + universe,
            (tenant, module),
        )
        m = cur.fetchone()
        matrix_boxes, matrix_images = int(m["boxes"]), int(m["images"])
    finally:
        conn.close()

    print(f"EXPORT : {export_boxes} caixas | {export_images} imagens")
    print(f"MATRIZ : {matrix_boxes} caixas | {matrix_images} imagens")
    ok = export_boxes == matrix_boxes and export_images == matrix_images
    print("✅ BATE — a matriz conta idêntico ao export." if ok
          else "❌ DIVERGE — a matriz NÃO conta como o export.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
