"""
Recognition — Inventário R2 do acervo de treino (read-only).

Audita o acervo de frames de treino (public.training_frames) contra o
bucket R2: cada r2_key existe de fato (HEAD), pode ser baixado de fato
(GET completo em amostra), há órfãos (objetos no R2 sem linha no banco)
e há pesos de modelo esquecidos no bucket.

⚠️ SOMENTE LEITURA — HEAD, GET, list_objects_v2. Nunca put_object nem
delete_object. Nunca imprime/loga valores de credencial (R2_KEY,
R2_SECRET, DATABASE_URL) — só nomes das variáveis, nunca conteúdo.

Uso:
    export R2_ENDPOINT=... R2_BUCKET=... R2_KEY=... R2_SECRET=...
    export DATABASE_URL=postgresql://...
    python3 scripts/r2_inventory/inventory.py --out docs/quality/r2-inventory-YYYY-MM-DD.md

Etapas (a-f): extrai do DB -> HEAD concorrente -> GET de amostra + de
toda falha de HEAD -> lista bucket sob training-images/ e cruza com o
DB (órfãos) -> varre bucket inteiro por pesos de modelo -> relatório
markdown agregado (nunca item-a-item do acervo inteiro).
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import re
import subprocess
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

REQUIRED_ENV = ["R2_ENDPOINT", "R2_KEY", "R2_SECRET", "R2_BUCKET", "DATABASE_URL"]

WEIGHT_PATTERN = re.compile(
    r"\.(pth|pt|onnx|safetensors)$|sam|dino|grounding", re.IGNORECASE
)
TRAINING_PREFIX = "training-images/"

DEFAULT_HEAD_WORKERS = 24
DEFAULT_GET_SAMPLE = 30
DEFAULT_GET_WORKERS = 8

_KNOWN_WEIGHTS = [
    (re.compile(r"sam2", re.IGNORECASE), "SAM2", "Apache-2.0"),
    (re.compile(r"\bsam\b|sam_vit|sam-vit", re.IGNORECASE), "SAM (Segment Anything)", "Apache-2.0"),
    (re.compile(r"groundingdino|grounding[_-]?dino", re.IGNORECASE), "GroundingDINO", "Apache-2.0"),
    (re.compile(r"dinov2", re.IGNORECASE), "DINOv2", "Apache-2.0"),
    (re.compile(r"dino", re.IGNORECASE), "DINO (variante não identificada)", "verificar upstream"),
]


# --- Etapa 0: validação de ambiente ---------------------------------------

def require_env() -> dict[str, str]:
    """Exige as 5 variáveis. Erro claro (só nomes, nunca valores) se faltar."""
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        logger.error(
            "Variáveis de ambiente obrigatórias ausentes: %s", ", ".join(missing)
        )
        raise SystemExit(1)
    return {k: os.environ[k] for k in REQUIRED_ENV}


# --- Etapa a: extração do DB -----------------------------------------------

_FRAMES_QUERY = """
    SELECT tf.id::text AS id,
           tf.r2_key AS r2_key,
           tf.camera_id::text AS camera_id,
           tf.tenant_id::text AS tenant_id,
           COALESCE(t.slug, '(sem tenant)') AS tenant_slug,
           COALESCE(c.name, '(sem câmera)') AS camera_name,
           tf.created_at::date::text AS created_date
    FROM public.training_frames tf
    LEFT JOIN public.tenants t ON t.id = tf.tenant_id
    LEFT JOIN public.cameras c ON c.id = tf.camera_id
    ORDER BY tf.created_at
"""


def fetch_frames_psycopg2(database_url: str) -> list[dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(_FRAMES_QUERY)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_frames_psql(database_url: str) -> list[dict[str, Any]]:
    """Fallback via `psql -tA` quando psycopg2 não está disponível.

    Separador \\x01 (nunca aparece em r2_key/slug/nome) para tolerar
    valores com vírgula/pipe. DSN vai só no argv do subprocess — nunca
    logado; CalledProcessError é capturado sem propagar cmd/stderr
    (poderiam conter a DSN).
    """
    query = _FRAMES_QUERY.replace("\n", " ")
    try:
        result = subprocess.run(
            ["psql", database_url, "-tA", "-F", "\x01", "-c", query],
            capture_output=True,
            text=True,
            timeout=180,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("psql_failed: rc=%s (stderr omitido — pode conter DSN)", exc.returncode)
        raise SystemExit(1) from None
    except FileNotFoundError:
        logger.error("psql não encontrado e psycopg2 indisponível — instale um dos dois")
        raise SystemExit(1) from None

    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x01")
        if len(parts) != 7:
            continue
        fid, r2_key, camera_id, tenant_id, tenant_slug, camera_name, created_date = parts
        rows.append(
            {
                "id": fid,
                "r2_key": r2_key,
                "camera_id": camera_id or None,
                "tenant_id": tenant_id or None,
                "tenant_slug": tenant_slug or "(sem tenant)",
                "camera_name": camera_name or "(sem câmera)",
                "created_date": created_date or None,
            }
        )
    return rows


def fetch_frames(database_url: str) -> list[dict[str, Any]]:
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        logger.warning("psycopg2 indisponível — usando psql via subprocess")
        return fetch_frames_psql(database_url)
    return fetch_frames_psycopg2(database_url)


# --- Etapa b/c: HEAD concorrente + GET de amostra/falhas -------------------

def build_s3_client(env: dict[str, str], max_pool_connections: int = 40):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_KEY"],
        aws_secret_access_key=env["R2_SECRET"],
        region_name="auto",
        config=Config(
            retries={"max_attempts": 3},
            connect_timeout=10,
            read_timeout=30,
            max_pool_connections=max_pool_connections,
        ),
    )


def head_one(client, bucket: str, key: str) -> tuple[str, str]:
    """Retorna (status, detalhe). status ∈ {ok, not_found, forbidden, error}."""
    from botocore.exceptions import ClientError

    try:
        client.head_object(Bucket=bucket, Key=key)
        return ("ok", "")
    except ClientError as exc:
        meta = exc.response.get("ResponseMetadata", {})
        status_code = meta.get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code", "")
        if status_code == 404 or code in ("404", "NoSuchKey", "NotFound"):
            return ("not_found", code or "404")
        if status_code == 403 or code in ("403", "AccessDenied"):
            return ("forbidden", code or "403")
        return ("error", code or str(status_code))
    except Exception as exc:  # noqa: BLE001 - precisa capturar timeout/rede também
        return ("error", type(exc).__name__)


def head_all(client, bucket: str, frames: list[dict[str, Any]], workers: int) -> dict[str, tuple[str, str]]:
    """HEAD concorrente em todos os r2_key. Retorna {frame_id: (status, detalhe)}."""
    results: dict[str, tuple[str, str]] = {}
    total = len(frames)
    done = 0
    log_every = max(1, total // 10)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(head_one, client, bucket, f["r2_key"]): f["id"] for f in frames
        }
        for fut in as_completed(futures):
            fid = futures[fut]
            results[fid] = fut.result()
            done += 1
            if done % log_every == 0 or done == total:
                logger.info("HEAD progresso: %d/%d", done, total)
    return results


def get_one(client, bucket: str, key: str) -> tuple[bool, str, int]:
    """GET completo (baixa e descarta o corpo). Retorna (ok, detalhe, bytes)."""
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"]
        total_bytes = 0
        while True:
            chunk = body.read(1024 * 1024)
            if not chunk:
                break
            total_bytes += len(chunk)
        return (True, "", total_bytes)
    except Exception as exc:  # noqa: BLE001
        return (False, type(exc).__name__, 0)


def get_verify(
    client, bucket: str, keys: list[tuple[str, str]], workers: int
) -> list[dict[str, Any]]:
    """GET real (não HEAD) para uma lista de (frame_id, r2_key)."""
    out: list[dict[str, Any]] = []
    if not keys:
        return out
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(get_one, client, bucket, key): (fid, key) for fid, key in keys
        }
        for fut in as_completed(futures):
            fid, key = futures[fut]
            ok, detail, nbytes = fut.result()
            out.append({"frame_id": fid, "r2_key": key, "ok": ok, "detail": detail, "bytes": nbytes})
    return out


# --- Etapa d/e: uma única varredura do bucket inteiro -----------------------

def scan_bucket(client, bucket: str) -> tuple[set[str], list[tuple[str, int]], int]:
    """Uma paginação sobre o bucket inteiro (read-only: list_objects_v2).

    Retorna: (chaves sob training-images/, [(chave_peso, tamanho), ...], total_objetos).
    """
    paginator = client.get_paginator("list_objects_v2")
    training_keys: set[str] = set()
    weight_matches: list[tuple[str, int]] = []
    total_objects = 0
    pages = 0

    for page in paginator.paginate(Bucket=bucket):
        pages += 1
        for obj in page.get("Contents", []):
            key = obj["Key"]
            size = int(obj.get("Size", 0))
            total_objects += 1
            if key.startswith(TRAINING_PREFIX):
                training_keys.add(key)
            if WEIGHT_PATTERN.search(key):
                weight_matches.append((key, size))
        if pages % 20 == 0:
            logger.info("list_objects_v2 progresso: %d páginas, %d objetos até agora", pages, total_objects)

    logger.info("list_objects_v2 concluído: %d objetos em %d páginas", total_objects, pages)
    return training_keys, weight_matches, total_objects


def classify_weight(key: str) -> tuple[str, str]:
    for pattern, variant, license_note in _KNOWN_WEIGHTS:
        if pattern.search(key):
            return (variant, license_note)
    return ("desconhecido", "verificar upstream")


def human_size(nbytes: int) -> str:
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


# --- Etapa f: relatório -----------------------------------------------------

def build_report(
    *,
    frames: list[dict[str, Any]],
    head_results: dict[str, tuple[str, str]],
    get_sample_results: list[dict[str, Any]],
    get_failure_results: list[dict[str, Any]],
    training_keys_in_r2: set[str],
    weight_matches: list[tuple[str, int]],
    total_bucket_objects: int,
    bucket: str,
    elapsed_seconds: float,
    report_date: str,
) -> str:
    total = len(frames)
    status_counts = Counter(head_results[f["id"]][0] for f in frames)
    ok = status_counts.get("ok", 0)
    not_found = status_counts.get("not_found", 0)
    forbidden = status_counts.get("forbidden", 0)
    error = status_counts.get("error", 0)

    # Quebra por dia
    by_day: dict[str, Counter] = defaultdict(Counter)
    for f in frames:
        day = f.get("created_date") or "(sem data)"
        by_day[day][head_results[f["id"]][0]] += 1

    # Quebra por câmera
    by_camera: dict[str, Counter] = defaultdict(Counter)
    for f in frames:
        cam = f.get("camera_name") or "(sem câmera)"
        by_camera[cam][head_results[f["id"]][0]] += 1

    # Quebra por tenant
    by_tenant: dict[str, Counter] = defaultdict(Counter)
    for f in frames:
        tslug = f.get("tenant_slug") or "(sem tenant)"
        by_tenant[tslug][head_results[f["id"]][0]] += 1

    # Órfãos
    db_r2_keys = {f["r2_key"] for f in frames if f.get("r2_key")}
    orphans = training_keys_in_r2 - db_r2_keys
    orphans_by_tenant: Counter = Counter()
    for key in orphans:
        parts = key.split("/")
        tenant_part = parts[1] if len(parts) > 1 else "(desconhecido)"
        orphans_by_tenant[tenant_part] += 1

    lines: list[str] = []
    lines.append(f"# Inventário R2 do acervo de treino — {report_date}")
    lines.append("")
    lines.append(
        f"Bucket `{bucket}` · {total} frames em `public.training_frames` · "
        f"tempo total de execução: {elapsed_seconds:.0f}s."
    )
    lines.append("")

    lines.append("## Tabela geral")
    lines.append("")
    lines.append("| Métrica | Contagem | % do total |")
    lines.append("|---|---|---|")
    lines.append(f"| Frames no DB | {total} | 100% |")
    lines.append(f"| Com objeto no R2 (HEAD 200) | {ok} | {ok / total * 100:.1f}% |" if total else "| Com objeto no R2 | 0 | - |")
    lines.append(f"| Faltando (HEAD 404) | {not_found} | {not_found / total * 100:.1f}% |" if total else "| Faltando | 0 | - |")
    lines.append(f"| Acesso negado (HEAD 403) | {forbidden} | {forbidden / total * 100:.1f}% |" if total else "| Acesso negado | 0 | - |")
    lines.append(f"| Outro erro | {error} | {error / total * 100:.1f}% |" if total else "| Outro erro | 0 | - |")
    lines.append("")

    lines.append("## Quebra por dia")
    lines.append("")
    lines.append("| Data | Frames | OK | Faltando | Outro erro |")
    lines.append("|---|---|---|---|---|")
    for day in sorted(by_day.keys()):
        c = by_day[day]
        total_day = sum(c.values())
        bad = c.get("error", 0) + c.get("forbidden", 0)
        lines.append(f"| {day} | {total_day} | {c.get('ok', 0)} | {c.get('not_found', 0)} | {bad} |")
    lines.append("")

    lines.append("## Quebra por câmera")
    lines.append("")
    lines.append("| Câmera | Frames | OK | Faltando | Outro erro |")
    lines.append("|---|---|---|---|---|")
    for cam in sorted(by_camera.keys(), key=lambda c: -sum(by_camera[c].values())):
        c = by_camera[cam]
        total_cam = sum(c.values())
        bad = c.get("error", 0) + c.get("forbidden", 0)
        lines.append(f"| {cam} | {total_cam} | {c.get('ok', 0)} | {c.get('not_found', 0)} | {bad} |")
    lines.append("")

    lines.append("## Quebra por tenant")
    lines.append("")
    lines.append("| Tenant (slug) | Frames | OK | Faltando | Outro erro |")
    lines.append("|---|---|---|---|---|")
    for t in sorted(by_tenant.keys(), key=lambda t: -sum(by_tenant[t].values())):
        c = by_tenant[t]
        total_t = sum(c.values())
        bad = c.get("error", 0) + c.get("forbidden", 0)
        lines.append(f"| {t} | {total_t} | {c.get('ok', 0)} | {c.get('not_found', 0)} | {bad} |")
    lines.append("")

    lines.append("## Falhas individuais (HEAD != ok)")
    lines.append("")
    failures = [f for f in frames if head_results[f["id"]][0] != "ok"]
    if not failures:
        lines.append("Nenhuma falha de HEAD — todos os frames têm objeto correspondente no R2.")
    elif len(failures) <= 30:
        lines.append("| frame_id | r2_key | status | detalhe |")
        lines.append("|---|---|---|---|")
        for f in failures:
            status, detail = head_results[f["id"]]
            lines.append(f"| {f['id']} | `{f['r2_key']}` | {status} | {detail} |")
    else:
        lines.append(
            f"{len(failures)} falhas — acima do limite de listagem individual (30). "
            "Ver contagens agregadas acima (por dia/câmera/tenant)."
        )
    lines.append("")

    lines.append("## Amostra GET (prova de download real)")
    lines.append("")
    n_sample = len(get_sample_results)
    n_sample_ok = sum(1 for r in get_sample_results if r["ok"])
    lines.append(
        f"{n_sample_ok}/{n_sample} downloads completos bem-sucedidos na amostra aleatória "
        f"de {n_sample} objetos marcados OK no HEAD."
    )
    if get_sample_results:
        avg_bytes = sum(r["bytes"] for r in get_sample_results if r["ok"]) / max(n_sample_ok, 1)
        lines.append(f"Tamanho médio dos objetos baixados: {human_size(avg_bytes)}.")
    sample_failures = [r for r in get_sample_results if not r["ok"]]
    if sample_failures:
        lines.append("")
        lines.append("Falhas de GET na amostra:")
        lines.append("")
        lines.append("| frame_id | r2_key | detalhe |")
        lines.append("|---|---|---|")
        for r in sample_failures:
            lines.append(f"| {r['frame_id']} | `{r['r2_key']}` | {r['detail']} |")
    lines.append("")

    if get_failure_results:
        lines.append("## GET em toda falha de HEAD (confirma que 404/403 é real, não falso-negativo)")
        lines.append("")
        lines.append("| frame_id | r2_key | GET ok? | detalhe |")
        lines.append("|---|---|---|---|")
        for r in get_failure_results:
            lines.append(f"| {r['frame_id']} | `{r['r2_key']}` | {'sim' if r['ok'] else 'não'} | {r['detail']} |")
        lines.append("")

    lines.append("## Órfãos (objetos no R2 sob `training-images/` sem linha no DB)")
    lines.append("")
    lines.append(
        f"{len(orphans)} objetos no bucket sob `{TRAINING_PREFIX}` não correspondem a "
        f"nenhum `r2_key` em `public.training_frames` "
        f"(bucket tem {len(training_keys_in_r2)} objetos sob esse prefixo; DB tem {len(db_r2_keys)} r2_keys)."
    )
    if orphans_by_tenant:
        lines.append("")
        lines.append("| Segmento do prefixo (tenant/slug na chave) | Órfãos |")
        lines.append("|---|---|")
        for seg, count in orphans_by_tenant.most_common():
            lines.append(f"| {seg} | {count} |")
    lines.append("")

    lines.append("## Pesos de modelo no bucket")
    lines.append("")
    lines.append(
        f"Varredura do bucket inteiro ({total_bucket_objects} objetos) por chaves "
        "casando `.pth|.pt|.onnx|.safetensors` ou contendo `sam`/`dino`/`grounding` "
        "(case-insensitive)."
    )
    lines.append("")
    if not weight_matches:
        lines.append("**Pesos NÃO estão no R2.** Nenhuma chave casou com o padrão de busca.")
    else:
        lines.append(f"{len(weight_matches)} chave(s) encontrada(s):")
        lines.append("")
        lines.append("| Chave | Tamanho | Variante inferida | Licença upstream |")
        lines.append("|---|---|---|---|")
        for key, size in sorted(weight_matches):
            variant, license_note = classify_weight(key)
            lines.append(f"| `{key}` | {human_size(size)} | {variant} | {license_note} |")
        lines.append("")
        lines.append(
            "Ressalva: licença é a do release oficial upstream (SAM/SAM2 e "
            "GroundingDINO: Apache-2.0; DINOv2: Apache-2.0) — um checkpoint "
            "derivado/fine-tunado pode divergir do upstream; confirmar "
            "proveniência antes de qualquer uso comercial do checkpoint em si."
        )
    lines.append("")

    return "\n".join(lines) + "\n"


# --- main --------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Caminho do relatório markdown de saída")
    parser.add_argument("--head-workers", type=int, default=DEFAULT_HEAD_WORKERS)
    parser.add_argument("--get-sample", type=int, default=DEFAULT_GET_SAMPLE)
    parser.add_argument("--get-workers", type=int, default=DEFAULT_GET_WORKERS)
    parser.add_argument("--seed", type=int, default=None, help="Seed do random.sample (reprodutibilidade)")
    args = parser.parse_args()

    env = require_env()
    if args.seed is not None:
        random.seed(args.seed)

    t0 = time.monotonic()

    logger.info("Etapa a: extraindo frames do DB...")
    frames = fetch_frames(env["DATABASE_URL"])
    logger.info("frames_extraidos: %d", len(frames))
    if not frames:
        logger.error("Nenhum frame encontrado em public.training_frames — abortando")
        raise SystemExit(1)

    client = build_s3_client(env, max_pool_connections=max(args.head_workers, args.get_workers) + 8)
    bucket = env["R2_BUCKET"]

    logger.info("Etapa b: HEAD concorrente (%d workers)...", args.head_workers)
    head_results = head_all(client, bucket, frames, args.head_workers)

    ok_ids = [f["id"] for f in frames if head_results[f["id"]][0] == "ok"]
    fail_frames = [f for f in frames if head_results[f["id"]][0] != "ok"]

    logger.info("Etapa c: GET de amostra (%d) + toda falha de HEAD (%d)...", min(args.get_sample, len(ok_ids)), len(fail_frames))
    sample_ids = set(random.sample(ok_ids, min(args.get_sample, len(ok_ids))))
    sample_keys = [(f["id"], f["r2_key"]) for f in frames if f["id"] in sample_ids]
    failure_keys = [(f["id"], f["r2_key"]) for f in fail_frames]

    get_sample_results = get_verify(client, bucket, sample_keys, args.get_workers)
    get_failure_results = get_verify(client, bucket, failure_keys, args.get_workers)

    logger.info("Etapa d/e: varredura do bucket inteiro (list_objects_v2)...")
    training_keys_in_r2, weight_matches, total_bucket_objects = scan_bucket(client, bucket)

    elapsed = time.monotonic() - t0
    report_date = Path(args.out).stem.split("r2-inventory-")[-1] or time.strftime("%Y-%m-%d")

    logger.info("Etapa f: gerando relatório...")
    report = build_report(
        frames=frames,
        head_results=head_results,
        get_sample_results=get_sample_results,
        get_failure_results=get_failure_results,
        training_keys_in_r2=training_keys_in_r2,
        weight_matches=weight_matches,
        total_bucket_objects=total_bucket_objects,
        bucket=bucket,
        elapsed_seconds=elapsed,
        report_date=report_date,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    logger.info("relatorio_gerado: %s (%.0fs total)", out_path, elapsed)


if __name__ == "__main__":
    main()
