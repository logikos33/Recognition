#!/usr/bin/env python3
"""Imagens reais da RVB, anonimizadas, para material comercial — pipeline local.

SOMENTE LEITURA no R2 (list/get) e no banco (SELECT). Nada é escrito fora da
pasta `--out`. Nenhum valor de credencial é impresso, logado ou gravado.

Fonte da verdade da "detecção acontecendo": a evidência no R2 é o frame CRU
(`evidence/<camera_id>/<ts>.jpg`, ver `edge/routes.py::upload_camera_evidence`
e `inference._save_alert`); a caixa mora em `alerts.violations` (JSONB) com
`bbox_unidade` ∈ {pixels_xywh_frame_original, pixels_xywh_streammux(+frame_wh)}
— a mesma projeção de `apps/frontend/src/services/bboxProjecao.ts`.

Credenciais, só por ENV (nunca argv):
    R2_ENDPOINT R2_BUCKET            (obrigatórias para R2)
    R2_RO_ACCESS_KEY R2_RO_SECRET    (preferidas — token Object Read only)
    R2_KEY R2_SECRET                 (fallback: credencial da API-V3)
    DATABASE_URL                     (SELECT em alerts/cameras/tenants)

Uso típico (fora do repo, numa pasta nova):
    eval "$(railway variables -s API-V3 -e Desenvolvimento --kv \\
            | grep -E '^(R2_|DATABASE_URL)' | sed 's/^/export /')"
    python3 rvb_anon_material.py tudo --out ~/material-comercial/rvb-anon
    # etapas separadas: inventario | candidatos | selecionar | render | contato | relatorio
    python3 rvb_anon_material.py --autoteste    # offline, sem credencial

Cobertura manual de identificadores (logo, placa, crachá, texto): depois da
revisão visual, escreva `<out>/cobrir.json` como
    {"rvb-anon-01.png": [[x, y, w, h], ...]}   # fração 0..1 da imagem final
e rode `render` de novo; o retângulo sólido entra na imagem e na tabela.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("rvb-anon")

# ── parâmetros (decisões registradas) ───────────────────────────────────────
NITIDEZ_MIN = 150.0            # mesmo limiar do replay_miner (_DEFAULT_BLUR_VARIANCE_MIN)
MAX_CANDIDATOS = 40
FINAIS_MIN, FINAIS_MAX = 6, 8
MIN_CAMERAS = 3
MAX_POR_CAMERA_FINAL = 3
JANELA_LOCAL = [(5, 16), (17, 19)]   # horas locais (America/Sao_Paulo) inclusivas
TZ_LOCAL_FALLBACK = timezone(timedelta(hours=-3))
RAIO_BLUR_MIN_PX = 25          # prompt: raio ≥ 25 px no tamanho original
PIXEL_BLOCO = 12               # pixelização antes do gaussiano (cinto e suspensório)
LIST_CAP_POR_PREFIXO = 60_000  # teto de paginação no inventário (só contagem)

BBOX_FRAME_ORIGINAL = "pixels_xywh_frame_original"
BBOX_STREAMMUX = "pixels_xywh_streammux"

# classes cuja caixa está na CABEÇA — a parte de baixo delas é rosto.
CLASSES_CABECA = {
    "helmet", "no_helmet", "glasses", "no_glasses", "mask", "no_mask",
    "Capacete", "Sem Capacete", "Oculos", "Sem Oculos", "Mascara", "Sem Mascara",
    "Óculos", "Sem Óculos", "Máscara", "Sem Máscara",
}
ROTULO_PT = {
    "helmet": "Capacete", "no_helmet": "Sem capacete",
    "vest": "Colete", "no_vest": "Sem colete",
    "gloves": "Luvas", "no_gloves": "Sem luvas",
    "glasses": "Óculos", "no_glasses": "Sem óculos",
    "mask": "Máscara", "no_mask": "Sem máscara",
    "boots": "Botas", "no_boots": "Sem botas",
    "person": "Pessoa",
}
COR_OK = (80, 200, 120)        # BGR verde
COR_VIOLACAO = (60, 60, 230)   # BGR vermelho
COR_COBERTURA = (20, 20, 20)


def _tz_local():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Sao_Paulo")
    except Exception:  # noqa: BLE001 — sem tzdata, UTC-3 fixo
        return TZ_LOCAL_FALLBACK


def _hora_local(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)   # alerts.timestamp é TIMESTAMP (UTC do Postgres)
    return ts.astimezone(_tz_local())


def _na_janela(ts_local: datetime) -> bool:
    return any(a <= ts_local.hour <= b for a, b in JANELA_LOCAL)


def _eh_violacao(classe: str) -> bool:
    c = str(classe)
    return c.startswith("no_") or c.startswith("Sem ") or c.startswith("Uso ")


# ── credenciais / clientes (nunca imprimem valores) ─────────────────────────
def _env_r2() -> dict[str, str]:
    faltam = [k for k in ("R2_ENDPOINT", "R2_BUCKET") if not os.environ.get(k)]
    key, sec = os.environ.get("R2_RO_ACCESS_KEY"), os.environ.get("R2_RO_SECRET")
    origem = "R2_RO_*"
    if not (key and sec):
        key, sec, origem = os.environ.get("R2_KEY"), os.environ.get("R2_SECRET"), "R2_KEY/R2_SECRET"
    if not (key and sec):
        faltam.append("R2_RO_ACCESS_KEY+R2_RO_SECRET ou R2_KEY+R2_SECRET")
    if faltam:
        log.error("variáveis ausentes: %s", ", ".join(faltam))
        raise SystemExit(2)
    log.info("credencial R2: %s (valor não exibido)", origem)
    return {"endpoint": os.environ["R2_ENDPOINT"], "bucket": os.environ["R2_BUCKET"],
            "key": key, "secret": sec}


def _s3(env: dict[str, str]):
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3", endpoint_url=env["endpoint"], aws_access_key_id=env["key"],
        aws_secret_access_key=env["secret"], region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3},
                      connect_timeout=10, read_timeout=60),
    )


def _classe_erro(exc: BaseException) -> str:
    return type(exc).__name__   # nunca str(exc): pode carregar URL/credencial


# ── etapa 0: inventário do bucket ───────────────────────────────────────────
def _tipo_da_chave(k: str) -> str:
    kl = k.lower()
    if kl.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return "frame"
    if kl.endswith((".mp4", ".mkv", ".ts", ".m3u8")):
        return "clipe"
    if kl.endswith(".json"):
        return "json"
    if kl.endswith((".pth", ".pt", ".onnx", ".engine", ".safetensors")):
        return "peso"
    if kl.endswith((".txt", ".yaml", ".yml", ".csv", ".log")):
        return "texto"
    return "outro"


def inventario(out: Path) -> None:
    env = _env_r2()
    s3 = _s3(env)
    pag = s3.get_paginator("list_objects_v2")
    prefixos: list[str] = []
    soltos = 0
    try:
        for page in pag.paginate(Bucket=env["bucket"], Delimiter="/"):
            prefixos += [cp["Prefix"] for cp in page.get("CommonPrefixes", [])]
            soltos += len(page.get("Contents", []))
    except Exception as exc:  # noqa: BLE001
        log.error("list raiz falhou (%s) — cheque permissão/bucket", _classe_erro(exc))
        raise SystemExit(3) from None

    linhas = []
    detalhe: dict[str, Any] = {}
    for p in sorted(prefixos):
        n, tipos, amostra, ult = 0, Counter(), [], None
        for page in pag.paginate(Bucket=env["bucket"], Prefix=p):
            for o in page.get("Contents", []):
                n += 1
                tipos[_tipo_da_chave(o["Key"])] += 1
                if len(amostra) < 20 and random.random() < 0.05 or len(amostra) < 3:
                    amostra.append(o["Key"])
                lm = o.get("LastModified")
                if lm and (ult is None or lm > ult):
                    ult = lm
            if n >= LIST_CAP_POR_PREFIXO:
                break
        tipo = ", ".join(f"{t}×{c}" for t, c in tipos.most_common(3)) or "-"
        exemplo = amostra[0] if amostra else "-"
        capped = "≥" if n >= LIST_CAP_POR_PREFIXO else ""
        linhas.append(f"| `{p}` | {capped}{n} | {tipo} | {ult.date() if ult else '-'} | `{exemplo}` |")
        detalhe[p] = {"n": n, "capped": bool(capped), "tipos": dict(tipos), "amostra": amostra,
                      "ultimo": ult.isoformat() if ult else None}
        log.info("prefixo %s: %s%d objetos", p, capped, n)

    # sub-prefixos de evidence/ (uma pasta por câmera)
    cams = []
    if "evidence/" in detalhe:
        for page in pag.paginate(Bucket=env["bucket"], Prefix="evidence/", Delimiter="/"):
            cams += [cp["Prefix"] for cp in page.get("CommonPrefixes", [])]
        detalhe["evidence/"]["cameras"] = len(cams)

    md = ["# Inventário do bucket R2 (somente leitura)", "",
          f"Gerado em {datetime.now(timezone.utc).isoformat(timespec='seconds')} · "
          f"bucket: `{env['bucket']}` · objetos soltos na raiz: {soltos} · "
          f"sub-prefixos em `evidence/` (câmeras): {len(cams)}", "",
          "| prefixo | nº objetos | tipo (ext×n) | último objeto | exemplo de chave |",
          "|---|---|---|---|---|", *linhas, ""]
    (out / "inventario-bucket.md").write_text("\n".join(md), encoding="utf-8")
    (out / "inventario-bucket.json").write_text(json.dumps(detalhe, indent=1, default=str), encoding="utf-8")
    log.info("inventário gravado em %s", out / "inventario-bucket.md")


# ── etapa 1: candidatos (DB → R2) ───────────────────────────────────────────
_SQL_ALERTAS = """
SELECT a.id::text, a.camera_id::text, COALESCE(c.name, '(sem nome)') AS camera_name,
       a.evidence_key, a.violations::text, a.confidence, a.timestamp::text,
       COALESCE(a.verification_verdict, '') AS verdict, COALESCE(a.verified_by, '') AS verified_by
FROM public.alerts a
JOIN public.tenants t ON t.id = a.tenant_id
LEFT JOIN public.cameras c ON c.id = a.camera_id
WHERE t.slug = 'rvb'
  AND a.evidence_key IS NOT NULL AND a.evidence_key <> ''
  AND jsonb_typeof(a.violations) = 'array' AND jsonb_array_length(a.violations) > 0
  AND a.timestamp >= NOW() - INTERVAL '120 days'
ORDER BY a.timestamp DESC
LIMIT 6000
"""


def _rows_psql(dsn: str, sql: str) -> list[list[str]]:
    try:
        r = subprocess.run(["psql", dsn, "-tA", "-F", "\x01", "-c", sql.replace("\n", " ")],
                           capture_output=True, text=True, timeout=180, check=True)
    except subprocess.CalledProcessError as exc:
        log.error("psql falhou rc=%s (stderr omitido — pode conter DSN)", exc.returncode)
        raise SystemExit(4) from None
    return [ln.split("\x01") for ln in r.stdout.splitlines() if ln.strip()]


def _alertas_do_banco() -> list[dict[str, Any]]:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        log.error("DATABASE_URL ausente — sem ela não há caixa para desenhar (use --sem-db para frames crus)")
        raise SystemExit(2)
    try:
        import psycopg2
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(_SQL_ALERTAS)
                rows = [[("" if v is None else str(v)) for v in r] for r in cur.fetchall()]
        finally:
            conn.close()
    except ImportError:
        log.warning("psycopg2 indisponível — usando psql")
        rows = _rows_psql(dsn, _SQL_ALERTAS)
    except Exception as exc:  # noqa: BLE001
        log.error("conexão/consulta falhou (%s)", _classe_erro(exc))
        raise SystemExit(4) from None

    out = []
    for r in rows:
        if len(r) != 9:
            continue
        aid, cam, cam_name, key, viol, conf, ts, verdict, by = r
        try:
            viols = json.loads(viol) if viol else []
            tsd = datetime.fromisoformat(ts.replace(" ", "T"))
        except ValueError:
            continue
        out.append({"alert_id": aid, "camera_id": cam, "camera_name": cam_name, "evidence_key": key,
                    "violations": viols, "confidence": float(conf or 0), "timestamp_utc": ts,
                    "hora_local": _hora_local(tsd).isoformat(timespec="minutes"),
                    "verdict": verdict, "verified_by": by})
    log.info("alertas RVB com evidência e caixa: %d", len(out))
    return out


def _projetavel(v: dict) -> bool:
    b = v.get("bbox")
    if not (isinstance(b, list) and len(b) == 4):
        return False
    u = v.get("bbox_unidade")
    if u == BBOX_FRAME_ORIGINAL:
        return True
    if u == BBOX_STREAMMUX:
        wh = v.get("frame_wh") or []
        return len(wh) == 2 and wh[0] > 0 and wh[1] > 0
    return False


def _nitidez(img) -> float:
    import cv2
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def candidatos(out: Path, sem_db: bool = False, max_cand: int = MAX_CANDIDATOS) -> None:
    import cv2
    import numpy as np

    env = _env_r2()
    s3 = _s3(env)
    tmp = out / "tmp-candidatos"
    tmp.mkdir(parents=True, exist_ok=True)

    if sem_db:
        # fallback: só frames crus de evidence/<camera>/ (sem caixa → só para inventário visual)
        pag = s3.get_paginator("list_objects_v2")
        pool: list[dict[str, Any]] = []
        cams = [cp["Prefix"] for page in pag.paginate(Bucket=env["bucket"], Prefix="evidence/", Delimiter="/")
                for cp in page.get("CommonPrefixes", [])]
        for cp in cams:
            keys = [o["Key"] for page in pag.paginate(Bucket=env["bucket"], Prefix=cp) for o in page.get("Contents", [])]
            for k in keys[-400:]:
                ts_raw = Path(k).stem
                try:
                    tsd = datetime.strptime(ts_raw[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                pool.append({"alert_id": "", "camera_id": cp.split("/")[1], "camera_name": "(sem DB)",
                             "evidence_key": k, "violations": [], "confidence": 0.0,
                             "timestamp_utc": tsd.isoformat(), "hora_local": _hora_local(tsd).isoformat(timespec="minutes"),
                             "verdict": "", "verified_by": ""})
    else:
        pool = _alertas_do_banco()

    # filtros: janela diurna + ≥1 caixa projetável (quando há DB)
    elegiveis = []
    for a in pool:
        hl = datetime.fromisoformat(a["hora_local"])
        if not _na_janela(hl):
            continue
        proj = [v for v in a["violations"] if _projetavel(v)]
        if not sem_db and not proj:
            continue
        a["n_proj"] = len(proj)
        a["humano_aprovou"] = a["verdict"] == "approve" and a["verified_by"].startswith("user:")
        a["tem_violacao"] = any(_eh_violacao(v.get("class", "")) for v in proj)
        elegiveis.append(a)
    log.info("elegíveis (janela diurna, caixa projetável): %d em %d câmeras",
             len(elegiveis), len({a["camera_id"] for a in elegiveis}))

    # round-robin por câmera; dentro da câmera: aprovado por humano > nº caixas > confiança; espalha por dia
    por_cam: dict[str, list] = defaultdict(list)
    for a in elegiveis:
        por_cam[a["camera_id"]].append(a)
    for lst in por_cam.values():
        lst.sort(key=lambda a: (a["humano_aprovou"], a["n_proj"], a["confidence"]), reverse=True)
        vistos_dia: Counter = Counter()
        reord, resto = [], []
        for a in lst:
            d = a["hora_local"][:10]
            (reord if vistos_dia[d] < 2 else resto).append(a)
            vistos_dia[d] += 1
        lst[:] = reord + resto
    escolhidos: list[dict] = []
    while len(escolhidos) < max_cand and any(por_cam.values()):
        for cam in sorted(por_cam, key=lambda c: -len(por_cam[c])):
            if por_cam[cam] and len(escolhidos) < max_cand:
                escolhidos.append(por_cam[cam].pop(0))

    # download + nitidez
    linhas = []
    for i, a in enumerate(escolhidos, 1):
        dest = tmp / f"cand-{i:02d}.jpg"
        try:
            s3.download_file(env["bucket"], a["evidence_key"], str(dest))
        except Exception as exc:  # noqa: BLE001
            a.update({"nitidez": None, "ok": False, "motivo": f"download: {_classe_erro(exc)}"})
            continue
        img = cv2.imdecode(np.fromfile(str(dest), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            a.update({"nitidez": None, "ok": False, "motivo": "jpeg ilegível"})
            continue
        a["arquivo"] = dest.name
        a["wh"] = [int(img.shape[1]), int(img.shape[0])]
        a["nitidez"] = round(_nitidez(img), 1)
        a["ok"] = a["nitidez"] >= NITIDEZ_MIN and (sem_db or a["n_proj"] > 0)
        a["motivo"] = "" if a["ok"] else f"nitidez {a['nitidez']} < {NITIDEZ_MIN:.0f}"
        classes = Counter(v.get("class", "?") for v in a["violations"])
        linhas.append(
            f"| {i:02d} | {a['camera_name']} | {a['hora_local'][:16]} | "
            f"{', '.join(f'{c}×{n}' for c, n in classes.items()) or '-'} | {a['confidence']:.2f} | "
            f"{a['n_proj']} | {'sim' if a['humano_aprovou'] else '-'} | {a['nitidez']} | "
            f"{'✅' if a['ok'] else '❌ ' + a['motivo']} |"
        )
    md = ["# Candidatos (≤40, antes da seleção)", "",
          f"elegíveis={len(elegiveis)} · baixados={len(escolhidos)} · aprovados nitidez≥{NITIDEZ_MIN:.0f}="
          f"{sum(1 for a in escolhidos if a.get('ok'))} · câmeras={len({a['camera_id'] for a in escolhidos})}", "",
          "| nº | câmera | hora local | classes | conf | caixas projetáveis | humano aprovou | nitidez | ok |",
          "|---|---|---|---|---|---|---|---|---|", *linhas, ""]
    (out / "candidatos.md").write_text("\n".join(md), encoding="utf-8")
    (out / "candidatos.json").write_text(json.dumps(escolhidos, indent=1, default=str), encoding="utf-8")
    log.info("candidatos gravados em %s", out / "candidatos.md")


# ── etapa 1b: seleção dos finais ────────────────────────────────────────────
def selecionar(out: Path, n: int = FINAIS_MAX) -> None:
    cands = json.loads((out / "candidatos.json").read_text(encoding="utf-8"))
    ok = [c for c in cands if c.get("ok")]
    cams = sorted({c["camera_id"] for c in ok})
    if len(ok) < FINAIS_MIN or len(cams) < MIN_CAMERAS:
        log.error("insuficiente: %d candidatos ok em %d câmeras (mín %d em %d) — resultado negativo é válido",
                  len(ok), len(cams), FINAIS_MIN, MIN_CAMERAS)
        (out / "selecao.json").write_text("[]", encoding="utf-8")
        return
    # alterna violação / conforme, humano-aprovado primeiro, ≤3 por câmera, câmeras diferentes primeiro
    ok.sort(key=lambda c: (c["humano_aprovou"], c["n_proj"], c["nitidez"]), reverse=True)
    sel, por_cam, quer_viol = [], Counter(), True
    while len(sel) < n:
        achou = None
        for c in ok:
            if c in sel or por_cam[c["camera_id"]] >= MAX_POR_CAMERA_FINAL:
                continue
            if len({s["camera_id"] for s in sel}) < MIN_CAMERAS and c["camera_id"] in por_cam and len(sel) < MIN_CAMERAS:
                continue
            if c["tem_violacao"] == quer_viol:
                achou = c
                break
        if achou is None:
            achou = next((c for c in ok if c not in sel and por_cam[c["camera_id"]] < MAX_POR_CAMERA_FINAL), None)
        if achou is None:
            break
        sel.append(achou)
        por_cam[achou["camera_id"]] += 1
        quer_viol = not quer_viol
    for i, s in enumerate(sel, 1):
        s["final"] = f"rvb-anon-{i:02d}.png"
    (out / "selecao.json").write_text(json.dumps(sel, indent=1, default=str), encoding="utf-8")
    log.info("selecionados %d finais em %d câmeras", len(sel), len({s['camera_id'] for s in sel}))


# ── etapa 2: caixas + anonimização ──────────────────────────────────────────
def _carrega_cascades():
    import cv2
    base = Path(os.environ.get("HAAR_DIR", Path(__file__).resolve().parent / "haar"))
    nomes = ["haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml",
             "haarcascade_profileface.xml"]
    cascs = []
    for nm in nomes:
        p = base / nm
        if not p.exists():
            p = Path(cv2.data.haarcascades) / nm
        if p.exists():
            c = cv2.CascadeClassifier(str(p))
            if not c.empty():
                cascs.append((nm, c))
    if not cascs:
        log.error("nenhum Haar cascade encontrado (HAAR_DIR=%s) — anonimização de rosto indisponível", base)
        raise SystemExit(5)
    return cascs


def _iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    return inter / float(aw * ah + bw * bh - inter + 1e-9)


def detectar_rostos(img, cascs) -> list[list[int]]:
    """Haar frontal+alt2+perfil (e perfil espelhado), em 1× e 2× — rostos de CCTV são pequenos."""
    import cv2
    h, w = img.shape[:2]
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    achados: list[list[int]] = []
    for escala in (1.0, 2.0):
        g = gray if escala == 1.0 else cv2.resize(gray, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
        for nm, c in cascs:
            variantes = [(g, False)]
            if "profile" in nm:
                variantes.append((cv2.flip(g, 1), True))
            for gg, flip in variantes:
                dets = c.detectMultiScale(gg, scaleFactor=1.05, minNeighbors=4, minSize=(14, 14))
                for (x, y, bw, bh) in dets:
                    if flip:
                        x = gg.shape[1] - x - bw
                    achados.append([int(x / escala), int(y / escala), int(bw / escala), int(bh / escala)])
    # NMS simples
    achados.sort(key=lambda b: b[2] * b[3], reverse=True)
    final: list[list[int]] = []
    for b in achados:
        if all(_iou(b, f) < 0.3 for f in final):
            final.append(b)
    return final


def _anonimiza_regiao(img, x, y, w, h) -> tuple[float, float]:
    """Pixeliza + gaussiano forte (raio ≥25 px) na região; devolve (var_antes, var_depois)."""
    import cv2
    H, W = img.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return 0.0, 0.0
    roi = img[y0:y1, x0:x1]
    antes = _nitidez(roi) if roi.size else 0.0
    bloco = max(PIXEL_BLOCO, (x1 - x0) // 6)
    small = cv2.resize(roi, (max(1, (x1 - x0) // bloco), max(1, (y1 - y0) // bloco)), interpolation=cv2.INTER_LINEAR)
    pix = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
    k = max(2 * RAIO_BLUR_MIN_PX + 1, (max(x1 - x0, y1 - y0) // 2) | 1)
    img[y0:y1, x0:x1] = cv2.GaussianBlur(pix, (k, k), 0)
    depois = _nitidez(img[y0:y1, x0:x1])
    return antes, depois


def _desenha_caixa(img, bbox_px, classe: str, conf: float) -> None:
    import cv2
    x, y, w, h = (int(round(v)) for v in bbox_px)
    cor = COR_VIOLACAO if _eh_violacao(classe) else COR_OK
    esp = max(2, img.shape[1] // 640)
    cv2.rectangle(img, (x, y), (x + w, y + h), cor, esp)
    rotulo = ROTULO_PT.get(classe, classe)
    if conf:
        rotulo += f" {conf:.0%}"
    fs = max(0.5, img.shape[1] / 1920 * 0.7)
    (tw, th), bl = cv2.getTextSize(rotulo, cv2.FONT_HERSHEY_SIMPLEX, fs, esp)
    ty = y - 6 if y - th - 10 > 0 else y + h + th + 6
    cv2.rectangle(img, (x, ty - th - 6), (x + tw + 10, ty + bl - 2), cor, -1)
    cv2.putText(img, rotulo, (x + 5, ty - 2), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), esp, cv2.LINE_AA)


def _bbox_para_imagem(v: dict, W: int, H: int) -> list[float] | None:
    b = v.get("bbox")
    if not _projetavel(v):
        return None
    if v.get("bbox_unidade") == BBOX_FRAME_ORIGINAL:
        return [float(x) for x in b]
    fw, fh = v["frame_wh"]
    sx, sy = W / float(fw), H / float(fh)
    return [b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy]


def render(out: Path, blur_cabeca: bool = True) -> None:
    import cv2
    import numpy as np

    sel = json.loads((out / "selecao.json").read_text(encoding="utf-8"))
    if not sel:
        log.warning("selecao.json vazio — nada a renderizar")
        return
    cascs = _carrega_cascades()
    cobrir_path = out / "cobrir.json"
    cobrir = json.loads(cobrir_path.read_text(encoding="utf-8")) if cobrir_path.exists() else {}
    aceite = []
    for s in sel:
        src = out / "tmp-candidatos" / s["arquivo"]
        img = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_COLOR)
        H, W = img.shape[:2]

        # 1) rostos (no frame CRU, antes das caixas, para o detector não ver linhas)
        rostos = detectar_rostos(img, cascs)
        # 2) cabeças pelas caixas de classe de cabeça: 60% inferior = rosto
        cabecas = []
        if blur_cabeca:
            for v in s["violations"]:
                bp = _bbox_para_imagem(v, W, H)
                if bp and str(v.get("class")) in CLASSES_CABECA:
                    x, y, w, h = bp
                    cabecas.append([int(x - 0.1 * w), int(y + 0.4 * h), int(1.2 * w), int(0.7 * h)])
        regioes = rostos + [c for c in cabecas if all(_iou(c, r) < 0.5 for r in rostos)]
        desfocados = 0
        for (x, y, w, h) in regioes:
            # expande 30% e garante tamanho mínimo útil
            ex, ey = int(0.3 * w), int(0.3 * h)
            antes, depois = _anonimiza_regiao(img, x - ex, y - ey, w + 2 * ex, h + 2 * ey)
            if depois < max(20.0, 0.1 * antes) or antes == 0.0:
                desfocados += 1

        # 3) caixas do produto (depois do blur — a caixa fica nítida sobre o rosto borrado)
        n_caixas = 0
        for v in s["violations"]:
            bp = _bbox_para_imagem(v, W, H)
            if bp:
                _desenha_caixa(img, bp, str(v.get("class", "?")), float(v.get("confidence") or 0))
                n_caixas += 1

        # 4) cobertura manual (logo, placa, crachá, texto) — retângulo sólido
        cobertos = 0
        for (fx, fy, fw, fh) in cobrir.get(s["final"], []):
            cv2.rectangle(img, (int(fx * W), int(fy * H)), (int((fx + fw) * W), int((fy + fh) * H)), COR_COBERTURA, -1)
            cobertos += 1

        # 5) PNG via cv2 — sem EXIF/metadata; nome sem câmera/data/site
        dest = out / s["final"]
        cv2.imwrite(str(dest), img, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        aceite.append({
            "arquivo": s["final"], "camera_interno": s["camera_name"], "camera_id": s["camera_id"],
            "hora_local": s["hora_local"], "caixas_desenhadas": n_caixas,
            "rostos_detectados": len(regioes), "rostos_desfocados": desfocados,
            "rostos_haar": len(rostos), "cabecas_por_caixa": len(regioes) - len(rostos),
            "identificadores_cobertos": cobertos, "revisao_visual": "PENDENTE",
            "nitidez": s.get("nitidez"), "wh": [W, H],
        })
        log.info("%s ← %s · caixas=%d rostos=%d/%d cobertos=%d", s["final"], s["camera_name"],
                 n_caixas, desfocados, len(regioes), cobertos)
    (out / "aceite.json").write_text(json.dumps(aceite, indent=1, ensure_ascii=False), encoding="utf-8")


# ── contato ─────────────────────────────────────────────────────────────────
def contato(out: Path, cols: int = 3, largura: int = 640) -> None:
    import cv2
    import numpy as np

    finais = sorted(out.glob("rvb-anon-*.png"))
    if not finais:
        log.warning("sem finais para o contato")
        return
    tiles = []
    for p in finais:
        im = cv2.imread(str(p))
        h = int(im.shape[0] * largura / im.shape[1])
        t = cv2.resize(im, (largura, h))
        cv2.rectangle(t, (0, 0), (largura, 28), (0, 0, 0), -1)
        cv2.putText(t, p.name, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(t)
    th = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30)) for t in tiles]
    rows = []
    for i in range(0, len(tiles), cols):
        fila = tiles[i:i + cols]
        while len(fila) < cols:
            fila.append(np.full_like(tiles[0], 30))
        rows.append(np.hstack(fila))
    cv2.imwrite(str(out / "contact-sheet.png"), np.vstack(rows))
    log.info("contato gravado: %s (%d imagens)", out / "contact-sheet.png", len(finais))


# ── relatório ───────────────────────────────────────────────────────────────
def relatorio(out: Path, achados: Path | None = None) -> None:
    ac = json.loads((out / "aceite.json").read_text(encoding="utf-8")) if (out / "aceite.json").exists() else []
    md = ["# RELATÓRIO — imagens reais da RVB, anonimizadas (material comercial)", "",
          f"Gerado em {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC. "
          "Pipeline: `rvb_anon_material.py` (somente leitura no R2 e no banco; saída local).", ""]
    if achados and achados.exists():
        md += [achados.read_text(encoding="utf-8"), ""]
    md += ["## Tabela de aceite (bloco 2)", "",
           "| arquivo | câmera (interno) | hora local | caixas | rostos detectados | rostos desfocados | identificadores cobertos | revisão visual |",
           "|---|---|---|---|---|---|---|---|"]
    for a in ac:
        md.append(f"| {a['arquivo']} | {a['camera_interno']} | {a['hora_local'][:16]} | {a['caixas_desenhadas']} | "
                  f"{a['rostos_detectados']} (Haar {a['rostos_haar']} + cabeça/caixa {a['cabecas_por_caixa']}) | "
                  f"{a['rostos_desfocados']} | {a['identificadores_cobertos']} | {a['revisao_visual']} |")
    md += ["", f"Câmeras distintas nas finais: {len({a['camera_id'] for a in ac})} · finais: {len(ac)}", ""]
    for nome in ("inventario-bucket.md", "candidatos.md"):
        p = out / nome
        if p.exists():
            md += [p.read_text(encoding="utf-8"), ""]
    (out / "RELATORIO.md").write_text("\n".join(md), encoding="utf-8")
    log.info("relatório gravado: %s", out / "RELATORIO.md")


# ── autoteste offline ───────────────────────────────────────────────────────
def autoteste() -> None:
    import tempfile

    import cv2
    import numpy as np

    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        (out / "tmp-candidatos").mkdir()
        sel = []
        rng = np.random.default_rng(7)
        for i in range(1, 7):
            W, H = 1920, 1080
            img = np.full((H, W, 3), (90, 100, 110), np.uint8)
            img[:, :, 0] = rng.integers(60, 140, (H, W))
            cv2.rectangle(img, (800, 300), (900, 420), (200, 180, 160), -1)   # "cabeça"
            cv2.imwrite(str(out / "tmp-candidatos" / f"cand-{i:02d}.jpg"), img)
            viols = [{"class": "no_helmet" if i % 2 else "helmet", "confidence": 0.87,
                      "bbox": [533, 200, 67, 80], "bbox_unidade": BBOX_STREAMMUX, "frame_wh": [1280, 720]},
                     {"class": "vest", "confidence": 0.91, "bbox": [780, 430, 150, 260],
                      "bbox_unidade": BBOX_FRAME_ORIGINAL}]
            sel.append({"arquivo": f"cand-{i:02d}.jpg", "camera_id": f"cam-{(i % 3) + 1}", "camera_name": f"Canal {(i % 3) + 1}",
                        "hora_local": "2026-10-10T09:30", "violations": viols, "nitidez": 300.0,
                        "final": f"rvb-anon-{i:02d}.png"})
        (out / "selecao.json").write_text(json.dumps(sel), encoding="utf-8")
        (out / "cobrir.json").write_text(json.dumps({"rvb-anon-01.png": [[0.02, 0.02, 0.2, 0.08]]}), encoding="utf-8")
        render(out)
        contato(out)
        relatorio(out)
        ac = json.loads((out / "aceite.json").read_text(encoding="utf-8"))
        assert len(ac) == 6 and all(a["caixas_desenhadas"] == 2 for a in ac), ac
        assert ac[0]["identificadores_cobertos"] == 1
        assert all(a["rostos_detectados"] == a["rostos_desfocados"] for a in ac), ac
        img = cv2.imread(str(out / "rvb-anon-01.png"))
        # caixa do streammux projetada: x=533*1.5≈800 → pixel vermelho da borda
        assert img[300, 800].tolist() == list(COR_VIOLACAO) or img[299, 800].tolist() == list(COR_VIOLACAO), img[300, 800]
        # região da cabeça (60% inferior da caixa) ficou borrada: variância baixa
        assert _nitidez(img[352:392, 808:892]) < 50, _nitidez(img[352:392, 808:892])  # dentro da caixa, fora das bordas e do rótulo do colete
        assert (out / "contact-sheet.png").exists() and (out / "RELATORIO.md").exists()
        # PNG sem metadados textuais
        raw = (out / "rvb-anon-01.png").read_bytes()
        assert b"tEXt" not in raw and b"eXIf" not in raw
        # autoteste do seletor
        cands = []
        for i in range(12):
            cands.append({"ok": True, "camera_id": f"c{i % 4}", "humano_aprovou": i % 3 == 0, "n_proj": 1 + i % 2,
                          "nitidez": 200 + i, "tem_violacao": i % 2 == 0, "violations": [], "arquivo": "x"})
        (out / "candidatos.json").write_text(json.dumps(cands), encoding="utf-8")
        selecionar(out)
        s = json.loads((out / "selecao.json").read_text(encoding="utf-8"))
        assert FINAIS_MIN <= len(s) <= FINAIS_MAX and len({x["camera_id"] for x in s}) >= MIN_CAMERAS
        assert max(Counter(x["camera_id"] for x in s).values()) <= MAX_POR_CAMERA_FINAL
    print("AUTOTESTE: OK")


# ── CLI ─────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("etapa", nargs="?", choices=["tudo", "inventario", "candidatos", "selecionar", "render", "contato", "relatorio"])
    ap.add_argument("--out", type=Path, help="pasta de saída FORA do repo")
    ap.add_argument("--sem-db", action="store_true", help="sem DATABASE_URL: frames crus (sem caixa)")
    ap.add_argument("--max-candidatos", type=int, default=MAX_CANDIDATOS)
    ap.add_argument("--finais", type=int, default=FINAIS_MAX)
    ap.add_argument("--sem-blur-cabeca", action="store_true", help="não borrar a parte inferior das caixas de cabeça")
    ap.add_argument("--achados", type=Path, help="markdown com inventário/divergências para o topo do RELATORIO.md")
    ap.add_argument("--autoteste", action="store_true")
    args = ap.parse_args()

    if args.autoteste:
        autoteste()
        return
    if not args.etapa or not args.out:
        ap.error("informe a etapa e --out")
    out: Path = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (Path.cwd() / ".git").exists() and str(out).startswith(str(Path.cwd())):
        ap.error("--out dentro do repositório: imagens não entram no repo")

    etapas = ["inventario", "candidatos", "selecionar", "render", "contato", "relatorio"] if args.etapa == "tudo" else [args.etapa]
    for e in etapas:
        if e == "inventario":
            inventario(out)
        elif e == "candidatos":
            candidatos(out, sem_db=args.sem_db, max_cand=args.max_candidatos)
        elif e == "selecionar":
            selecionar(out, n=args.finais)
        elif e == "render":
            render(out, blur_cabeca=not args.sem_blur_cabeca)
        elif e == "contato":
            contato(out)
        elif e == "relatorio":
            relatorio(out, achados=args.achados)


if __name__ == "__main__":
    main()
