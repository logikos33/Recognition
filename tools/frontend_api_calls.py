#!/usr/bin/env python3
"""Quem consome o quê — cruza chamadas HTTP do frontend (e de edge/worker/scripts)
com o ``url_map`` real da API.

Por que existe
--------------
A migração do frontend exige saber, endpoint por endpoint, se o front ATUAL o
consome (com evidência arquivo:linha), se só edge/worker/scripts o chamam, ou se
ninguém chama. Este script extrai as chamadas do código-fonte (``api.get(...)``,
``fetch(...)``, ``src={`${API_BASE}/...`}``) e resolve cada uma com o matcher do
próprio Flask (``app.url_map.bind('').match``) — a mesma resolução de produção,
sem regex caseira de rota.

Uso
---
    cd services/api
    FLASK_ENV=testing python ../../tools/frontend_api_calls.py \
        --out ../../docs/migration/inventory

Saídas (determinísticas):
    consumers.json     — chamadas do front (resolvidas), sockets, outros consumidores,
                         env vars do front, e o índice por endpoint
    consumers.md       — resumo legível
    classification.json— rótulo PRELIMINAR por regra (FRONT-ATUAL / BACKEND-ONLY /
                         SEM-CONSUMIDOR) + evidências. "SEM-CONSUMIDOR" é dividido em
                         ÓRFÃO vs GAP-DE-PRODUTO por leitura humana/agente no mapa.

Limites (honestos)
------------------
- Caminhos montados dinamicamente (variável `path`, loops) saem como ``kind=dynamic``
  com o trecho bruto — não são resolvidos.
- ``${CONST}`` só é resolvido quando CONST é `const CONST = '<string>'` no mesmo
  arquivo (ou API_BASE/VITE_API_URL conhecidos).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "services" / "api"
FRONT_SRC = REPO_ROOT / "apps" / "frontend" / "src"

# Diretórios de consumidores NÃO-frontend → categoria
OTHER_CONSUMER_DIRS = {
    "services/edge-sync-agent": "edge",
    "services/edge-sync-agent/tests": "edge-tests",
    "deployments/edge": "edge",
    "deployments": "edge",
    "deepstream": "edge",
    "services/inference": "edge",
    "services/api/app/core": "api-internal",
    "services/api/app/domain": "api-internal",
    "services/api/app/infrastructure": "api-internal",
    "services/api/app/tasks": "worker",
    "services/api/app/worker": "worker",
    "services/api/app/celery": "worker",
    "services/api/celery_worker.py": "worker",
    "services/api/app/api": "api-internal",
    "scripts": "scripts",
    "tools": "scripts",
    "training": "training-scripts",
    "pre-annotation-service": "pre-annotation",
    "apps/landing": "landing",
    "apps/event-landing": "landing",
    "services/api/tests": "tests",
    "tests": "tests",
    "shared": "shared-lib",
    "shared/proto": "contract",
}
SKIP_DIR_PARTS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv", "docs", "graphify-out"}
SKIP_FILE_SUFFIX = (".md", ".json", ".lock", ".png", ".jpg", ".svg", ".pdf", ".txt", ".csv", ".log")

API_METHODS = ("get", "post", "put", "patch", "delete", "downloadBlob", "fetchRaw")
METHOD_MAP = {
    "get": "GET", "post": "POST", "put": "PUT", "patch": "PATCH", "delete": "DELETE",
    "downloadBlob": "GET", "fetchRaw": "GET",
}


# ----------------------------------------------------------------------------
# Parsing helpers (TS/TSX)
# ----------------------------------------------------------------------------

def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def _skip_generic(s: str, i: int) -> int:
    """Se s[i] == '<', pula o bloco genérico balanceado e retorna o índice após '>'."""
    if i >= len(s) or s[i] != "<":
        return i
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "<":
            depth += 1
        elif c == ">":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return i


def _read_string_literal(s: str, i: int):
    """Lê literal em s[i] ('...', "...", `...`). Retorna (raw, parts, end) ou None.

    parts: lista de ("lit", texto) | ("expr", código) para template literals.
    """
    if i >= len(s):
        return None
    q = s[i]
    if q not in "'\"`":
        return None
    j = i + 1
    parts: list[tuple[str, str]] = []
    buf = ""
    while j < len(s):
        c = s[j]
        if c == "\\":
            buf += s[j : j + 2]
            j += 2
            continue
        if q == "`" and c == "$" and j + 1 < len(s) and s[j + 1] == "{":
            if buf:
                parts.append(("lit", buf))
                buf = ""
            depth = 0
            k = j + 1
            while k < len(s):
                if s[k] == "{":
                    depth += 1
                elif s[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            parts.append(("expr", s[j + 2 : k].strip()))
            j = k + 1
            continue
        if c == q:
            if buf:
                parts.append(("lit", buf))
            return s[i : j + 1], parts, j + 1
        buf += c
        j += 1
    return None


def _module_consts(src: str) -> dict[str, str]:
    """`const NAME = '<string>'` / `const NAME = \\`<string sem ${}>\\`` no módulo."""
    out: dict[str, str] = {}
    for m in re.finditer(r"(?m)^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=\s*(['\"`])([^'\"`$]*)\2", src):
        out[m.group(1)] = m.group(3)
    return out


def _api_base_kind(src: str) -> str:
    """Como `API_BASE` se comporta neste arquivo:
    - 'root'  : const API_BASE = import.meta.env.VITE_API_URL (sem /api) → path absoluto
    - 'api'   : importado de services/api (já inclui /api)
    - 'none'  : não usa
    """
    m = re.search(r"const\s+API_BASE\s*=([^\n;]*(?:\n[^\n;]*){0,2})", src)
    if m:
        defn = m.group(1)
        if "/api" in defn:
            return "api"
        if "VITE_API_URL" in defn:
            return "root"
    if re.search(r"import\s*\{[^}]*\bAPI_BASE\b[^}]*\}\s*from\s*['\"][^'\"]*services/api['\"]", src):
        return "api"
    return "none"


def _resolve_parts(parts, consts: dict[str, str], api_base_kind: str, implicit_prefix: str) -> tuple[str, bool]:
    """Monta o path. Retorna (path, has_dynamic_param)."""
    out = implicit_prefix
    dynamic = False
    for kind, text in parts:
        if kind == "lit":
            out += text
        else:
            expr = text
            if expr in ("API_BASE",):
                out = "" if api_base_kind == "root" else "/api"
                continue
            if expr in ("import.meta.env.VITE_API_URL", "VITE_API_URL", "API_URL", "apiUrl", "baseUrl", "API_BASE_URL"):
                out = ""
                continue
            if expr in consts:
                out += consts[expr]
                continue
            # query string embutida (`${qs ? `?${qs}` : ''}`, `${params}`, `${tenantQs(id)}`) → descarta
            if ("?" in expr and ("`?" in expr or "'?" in expr or '"?' in expr)) or re.match(
                r"^(qs|query|queryString|params|search|tenantQs\(|buildQs\(|toQs\(|qsFrom)", expr
            ) or (not out.endswith("/") and re.search(r"\b(qs|query|params)\b", expr) and "/" not in expr):
                continue
            # encodeURIComponent(x) / String(x) / x.id → param
            out += "<param>"
            dynamic = True
    # strip query string
    out = out.split("?", 1)[0]
    return out, dynamic


def _walk_front_files():
    for p in sorted(FRONT_SRC.rglob("*")):
        if p.suffix not in (".ts", ".tsx"):
            continue
        rel = p.relative_to(REPO_ROOT).as_posix()
        if "/test/" in rel or rel.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")) or "__tests__" in rel:
            continue
        yield p, rel


def _line_of(src: str, idx: int) -> int:
    return src.count("\n", 0, idx) + 1


def extract_frontend_calls() -> tuple[list[dict], list[dict], list[dict]]:
    calls: list[dict] = []
    sockets: list[dict] = []
    envs: list[dict] = []
    for p, rel in _walk_front_files():
        src = p.read_text(encoding="utf-8", errors="replace")
        consts = _module_consts(src)
        base_kind = _api_base_kind(src)

        # 1) api.<method>(...)
        for m in re.finditer(r"\bapi\.(get|post|put|patch|delete|downloadBlob|fetchRaw)\b", src):
            meth = m.group(1)
            i = _skip_ws(src, m.end())
            i = _skip_generic(src, i)
            i = _skip_ws(src, i)
            if i >= len(src) or src[i] != "(":
                continue
            i = _skip_ws(src, i + 1)
            lit = _read_string_literal(src, i)
            line = _line_of(src, m.start())
            if lit is None:
                # argumento dinâmico: captura até a vírgula/parêntese
                snippet = src[i : i + 80].split("\n")[0]
                calls.append({"file": rel, "line": line, "kind": "dynamic", "via": f"api.{meth}", "method": METHOD_MAP[meth], "raw": snippet.strip(), "path": None})
                continue
            raw, parts, _ = lit
            path, dyn = _resolve_parts(parts, consts, base_kind, implicit_prefix="/api")
            http_method = METHOD_MAP[meth]
            if meth == "fetchRaw":
                mm = re.search(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", src[m.end() : m.end() + 400])
                if mm:
                    http_method = mm.group(1)
            calls.append({"file": rel, "line": line, "kind": "api", "via": f"api.{meth}", "method": http_method, "raw": raw, "path": path})

        # 2) fetch(`${API_BASE}...` | `${import.meta.env.VITE_API_URL}...`)
        for m in re.finditer(r"(?<![A-Za-z_.])fetch\s*\(", src):
            i = _skip_ws(src, m.end())
            lit = _read_string_literal(src, i)
            if lit is None:
                continue
            raw, parts, end = lit
            if not parts or parts[0][0] != "expr":
                continue
            path, dyn = _resolve_parts(parts, consts, base_kind, implicit_prefix="")
            if not path.startswith("/"):
                continue
            http_method = "GET"
            mm = re.search(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", src[end : end + 400])
            if mm:
                http_method = mm.group(1)
            calls.append({"file": rel, "line": _line_of(src, m.start()), "kind": "fetch", "via": "fetch", "method": http_method, "raw": raw, "path": path})

        # 3) outros templates `${API_BASE}/...` (src=, href=, new URL, hls) não capturados acima
        seen_spans = set()
        for m in re.finditer(r"`\$\{(?:API_BASE|import\.meta\.env\.VITE_API_URL|API_URL)\}[^`]*`", src):
            # pular se já faz parte de uma chamada api./fetch capturada (mesma linha)
            line = _line_of(src, m.start())
            if any(c["file"] == rel and c["line"] == line for c in calls):
                continue
            lit = _read_string_literal(src, m.start())
            if lit is None:
                continue
            raw, parts, _ = lit
            path, dyn = _resolve_parts(parts, consts, base_kind, implicit_prefix="")
            if not path.startswith("/") or path in ("/api", "/api<param>", "<param>", "/<param>") or (rel, line, path) in seen_spans:
                continue
            seen_spans.add((rel, line, path))
            calls.append({"file": rel, "line": line, "kind": "asset-url", "via": "template", "method": "GET", "raw": raw, "path": path})

        # 4) SocketIO: io(`${wsUrl}/ns`) + socket.on('evt') + socket.emit('evt')
        for m in re.finditer(r"\bio\(\s*(['\"`])([^'\"`]*)\1", src):
            ns_raw = m.group(2)
            ns = re.sub(r"\$\{[^}]*\}", "", ns_raw) or "/"
            on_events = sorted(set(re.findall(r"socket\.on\(\s*['\"]([^'\"]+)['\"]", src)))
            emit_events = sorted(set(re.findall(r"\.emit\(\s*['\"]([^'\"]+)['\"]", src)))
            sockets.append({"file": rel, "line": _line_of(src, m.start()), "namespace": ns, "on": on_events, "emit": emit_events})

        # 5) env vars
        for m in re.finditer(r"import\.meta\.env\.([A-Z_][A-Z0-9_]*)", src):
            envs.append({"file": rel, "line": _line_of(src, m.start()), "var": m.group(1)})

    calls.sort(key=lambda c: (c["file"], c["line"], c["method"], c.get("path") or ""))
    sockets.sort(key=lambda s: (s["file"], s["line"]))
    envs.sort(key=lambda e: (e["var"], e["file"], e["line"]))
    return calls, sockets, envs


# ----------------------------------------------------------------------------
# Outros consumidores (edge / worker / scripts / tests): literais com /api/...
# ----------------------------------------------------------------------------

API_PATH_RE = re.compile(r"/api/[A-Za-z0-9_\-/{}<>.:$\[\]]*")
INFRA_PATH_RE = re.compile(r"""["'`](/(?:health|livez|readyz|status|stream/[^"'`\s)]*))["'`]""")
_COMMENT_PREFIX = ("#", "//", "*", "/*")


def _hit_kind(src: str, idx: int) -> str:
    """'code' se o match está dentro de aspas na própria linha; senão 'prose' (comentário/docstring)."""
    ls = src.rfind("\n", 0, idx) + 1
    line = src[ls:idx]
    if line.strip().startswith(_COMMENT_PREFIX):
        return "prose"
    inside = any(line.count(q) % 2 == 1 for q in ("\"", "'", "`"))
    return "code" if inside else "prose"


def _category_for(rel: str) -> str | None:
    best = None
    for prefix, cat in OTHER_CONSUMER_DIRS.items():
        if rel == prefix or rel.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, cat)
    return best[1] if best else None


def extract_other_consumers() -> list[dict]:
    out: list[dict] = []
    for root, dirs, files in os.walk(REPO_ROOT):
        rel_root = Path(root).relative_to(REPO_ROOT).as_posix()
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIR_PARTS and not d.startswith("."))
        if rel_root.startswith("apps/frontend"):
            continue
        for fn in sorted(files):
            if fn.endswith(SKIP_FILE_SUFFIX):
                continue
            rel = f"{rel_root}/{fn}" if rel_root != "." else fn
            cat = _category_for(rel)
            if cat is None:
                continue
            # routes.py definem rotas, não consomem; os próprios scanners também não
            if rel.startswith("services/api/app/api/") and fn.endswith(("routes.py", "_routes.py")):
                continue
            if rel in ("tools/api_inventory.py", "tools/frontend_api_calls.py"):
                continue
            try:
                src = Path(root, fn).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits = [(m.start(), m.group(0)) for m in API_PATH_RE.finditer(src)]
            hits += [(m.start(1), m.group(1)) for m in INFRA_PATH_RE.finditer(src)]
            for idx, path in sorted(hits):
                path = path.rstrip(".,;:)]}`'\"")
                if path.startswith("/api/") and len(path) <= 5:
                    continue
                kind = _hit_kind(src, idx)
                # f-string {x}, %s, {} , <x> → <param>
                norm = re.sub(r"\{[^}]*\}|%s|%d|\$\{[^}]*\}|<[^>]+>", "<param>", path).split("?", 1)[0]
                out.append({"file": rel, "line": _line_of(src, idx), "category": cat, "kind": kind, "raw": path, "path": norm})
    out.sort(key=lambda c: (c["category"], c["file"], c["line"], c["path"]))
    return out


# ----------------------------------------------------------------------------
# Resolução com o matcher do Flask
# ----------------------------------------------------------------------------

def _make_app():
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("JWT_SECRET_KEY", "inventory-only-not-a-secret-" + "x" * 32)
    os.environ.setdefault("SECRET_KEY", "inventory-only-not-a-secret-" + "y" * 32)
    sys.path.insert(0, str(API_DIR))
    os.chdir(API_DIR)
    from app import create_app  # noqa: PLC0415

    return create_app("testing")


def _resolver(app):
    from werkzeug.routing import RequestRedirect  # noqa: PLC0415
    from werkzeug.exceptions import MethodNotAllowed, NotFound  # noqa: PLC0415

    adapter = app.url_map.bind("localhost")
    samples = ("1", "00000000-0000-4000-8000-000000000001", "x.m3u8")

    def resolve(path: str, method: str):
        if not path:
            return None, "empty"
        tried_405 = False
        for sample in samples:
            probe = path.replace("<param>", sample)
            try:
                endpoint, _args = adapter.match(probe, method=method)
            except RequestRedirect as rr:  # trailing slash etc.
                try:
                    endpoint, _args = adapter.match(rr.new_url.split("localhost", 1)[-1], method=method)
                except Exception:  # noqa: BLE001
                    continue
            except MethodNotAllowed:
                tried_405 = True
                continue
            except NotFound:
                continue
            if endpoint == "serve_frontend":
                # catch-all do SPA: só vale se for a raiz; qualquer outra coisa é 404 de API
                if probe in ("/",):
                    return endpoint, "ok"
                continue
            return endpoint, "ok"
        return None, ("405" if tried_405 else "404")

    return resolve


def rule_key(method: str, rule: str) -> str:
    return f"{method} {rule}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO_ROOT / "docs" / "migration" / "inventory"))
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    calls, sockets, envs = extract_frontend_calls()
    others = extract_other_consumers()

    app = _make_app()
    resolve = _resolver(app)
    endpoint_rules: dict[str, list[tuple[str, str]]] = defaultdict(list)  # endpoint → [(method, rule)]
    for rule in app.url_map.iter_rules():
        for m in sorted(x for x in (rule.methods or set()) if x not in ("HEAD", "OPTIONS")):
            endpoint_rules[rule.endpoint].append((m, rule.rule))

    def attach(c: dict):
        if c.get("path") is None:
            c["match"] = None
            c["match_status"] = "dynamic"
            return
        ep, status = resolve(c["path"], c["method"])
        c["match_status"] = status
        if ep:
            # a regra exata (método+rule) dentro do endpoint
            rules = [r for (m, r) in endpoint_rules[ep] if m == c["method"]]
            c["match"] = {"endpoint": ep, "rule": rules[0] if rules else None}
        else:
            c["match"] = None

    for c in calls:
        attach(c)
    for c in others:
        # método desconhecido em literais soltos → tenta GET depois POST/PUT/PATCH/DELETE
        ep = None
        for meth in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            ep, status = resolve(c["path"], meth)
            if ep:
                c["method_guess"] = meth
                break
        c["match_status"] = status
        c["match"] = {"endpoint": ep} if ep else None

    # Índice por regra (método+rule)
    per_rule: dict[str, dict] = {}
    for ep, rules in endpoint_rules.items():
        for m, r in rules:
            per_rule[rule_key(m, r)] = {"endpoint": ep, "frontend": [], "other": []}
    for c in calls:
        if c.get("match") and c["match"].get("rule"):
            k = rule_key(c["method"], c["match"]["rule"])
            per_rule[k]["frontend"].append({"file": c["file"], "line": c["line"], "via": c["via"], "kind": c["kind"]})
    for c in others:
        if c.get("match"):
            ep = c["match"]["endpoint"]
            for m, r in endpoint_rules[ep]:
                if m == c.get("method_guess"):
                    per_rule[rule_key(m, r)]["other"].append({"file": c["file"], "line": c["line"], "category": c["category"], "kind": c.get("kind")})
                    break

    # Classificação preliminar
    classification: list[dict] = []
    for rule in app.url_map.iter_rules():
        for m in sorted(x for x in (rule.methods or set()) if x not in ("HEAD", "OPTIONS")):
            k = rule_key(m, rule.rule)
            rec = per_rule[k]
            fe = rec["frontend"]
            oth = [o for o in rec["other"] if o["category"] not in ("tests", "edge-tests", "api-internal") and o.get("kind") == "code"]
            infra = rule.rule in ("/", "/<path:path>", "/health", "/livez", "/readyz", "/status", "/api/v1/health")
            edge_path = rule.rule.startswith(("/api/v1/edge", "/api/v1/devices", "/api/v1/site-gateways")) and not fe
            if fe:
                label = "FRONT-ATUAL"
            elif oth or infra or edge_path:
                label = "BACKEND-ONLY"
            else:
                label = "SEM-CONSUMIDOR"
            classification.append({
                "method": m,
                "path": rule.rule,
                "endpoint": rule.endpoint,
                "label_preliminar": label,
                "frontend_evidence": fe,
                "other_evidence": rec["other"],
            })
    classification.sort(key=lambda r: (r["path"], r["method"]))

    unmatched = [c for c in calls if c["kind"] != "dynamic" and not c.get("match")]
    dynamic = [c for c in calls if c["kind"] == "dynamic"]
    summary = {
        "frontend_calls_total": len(calls),
        "frontend_calls_matched": sum(1 for c in calls if c.get("match")),
        "frontend_calls_unmatched": len(unmatched),
        "frontend_calls_dynamic": len(dynamic),
        "frontend_sockets": len(sockets),
        "other_consumer_hits": len(others),
        "rules_total": len(classification),
        "by_label_preliminar": dict(sorted(
            __import__("collections").Counter(r["label_preliminar"] for r in classification).items()
        )),
        "frontend_env_vars": dict(sorted(__import__("collections").Counter(e["var"] for e in envs).items())),
    }

    (out / "consumers.json").write_text(json.dumps({
        "summary": summary,
        "frontend_calls": calls,
        "frontend_unmatched": unmatched,
        "frontend_dynamic": dynamic,
        "frontend_sockets": sockets,
        "frontend_env": envs,
        "other_consumers": others,
    }, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (out / "classification.json").write_text(json.dumps(classification, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    # Markdown resumo
    md = [
        "# Consumidores — gerado por `tools/frontend_api_calls.py`",
        "",
        f"- Chamadas do front extraídas: **{summary['frontend_calls_total']}** (casadas: {summary['frontend_calls_matched']}, "
        f"sem regra: {summary['frontend_calls_unmatched']}, dinâmicas: {summary['frontend_calls_dynamic']})",
        f"- Sockets do front: {summary['frontend_sockets']} · hits em edge/worker/scripts/tests: {summary['other_consumer_hits']}",
        f"- Rótulo preliminar por regra: {summary['by_label_preliminar']}",
        f"- Env vars do front: {summary['frontend_env_vars']}",
        "",
        "## Chamadas do front SEM regra correspondente (404/405 no matcher)",
        "",
        "| Arquivo:linha | Método | Path resolvido | Status | Raw |",
        "|---|---|---|---|---|",
    ]
    for c in unmatched:
        md.append(f"| `{c['file']}:{c['line']}` | {c['method']} | `{c['path']}` | {c['match_status']} | `{c['raw'][:80]}` |")
    md += ["", "## Chamadas dinâmicas (não resolvidas)", "", "| Arquivo:linha | Via | Trecho |", "|---|---|---|"]
    for c in dynamic:
        md.append(f"| `{c['file']}:{c['line']}` | {c['via']} | `{c['raw'][:80]}` |")
    md += ["", "## Sockets (cliente)", "", "| Arquivo:linha | Namespace | on | emit |", "|---|---|---|---|"]
    for s in sockets:
        md.append(f"| `{s['file']}:{s['line']}` | `{s['namespace']}` | {', '.join(s['on'])} | {', '.join(s['emit']) or '—'} |")
    (out / "consumers.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=1, ensure_ascii=False))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
