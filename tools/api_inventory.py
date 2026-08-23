#!/usr/bin/env python3
"""Inventário determinístico dos endpoints HTTP da API (Flask ``url_map``).

Por que existe
--------------
O mapa-contrato da migração do frontend (``docs/migration/MAPA-MIGRACAO-FRONTEND.md``)
precisa nascer do CÓDIGO REAL, não de grep nem de memória (C-04). Este script
importa ``create_app()`` e despeja o ``url_map`` completo — método · path ·
blueprint · função · arquivo:linha — e enriquece cada regra com uma análise
estática (AST) da view function: decorators, marcadores de auth, envelope de
resposta e marcadores de tenancy.

Os marcadores são HEURÍSTICA sobre o corpo da view (não descem em services /
repositories). Eles são a baseline reproduzível; a verificação linha a linha
fica registrada no mapa-contrato, não aqui.

Uso
---
    cd services/api
    FLASK_ENV=testing python ../../tools/api_inventory.py \
        --out ../../docs/migration/inventory

Saídas (determinísticas, ordenadas por path+método):
    endpoints.json   — lista de regras com todos os campos
    endpoints.md     — tabela legível
    summary.json     — contagens por blueprint / auth / envelope

Regras fora do ``url_map`` em TESTING (registradas só em produção):
    GET /api/v1/docs           — Swagger UI (flasgger, ``_configure_swagger``)
    GET /api/v1/apispec.json   — OpenAPI spec (idem)
Estão listadas em ``summary.json["not_in_testing_url_map"]`` para o mapa.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "services" / "api"

# Decorators que definem auth (nome → rótulo)
AUTH_DECORATORS = {
    "jwt_required": "jwt",
    "jwt_required_custom": "jwt",
    "require_superadmin": "superadmin",
    "require_superadmin_or_404": "superadmin(404)",
    "require_device_scope": "device_scope",
    "require_admin": "admin",
    "require_role": "role",
    "require_permission": "permission",
    "require_module": "module",
    "require_device_token": "device_token",
    "require_device_auth": "device_token",
    "require_worker_secret": "worker_secret",
    "require_internal_token": "internal_token",
    "require_api_key": "api_key",
}

# Marcadores no corpo da view (substring → rótulo)
AUTH_BODY_MARKERS = [
    ("verify_jwt_in_request", "jwt(inline)"),
    ("_require_jwt(", "jwt(helper)"),
    ("require_jwt(", "jwt(helper)"),
    ("_require_auth(", "jwt(helper)"),
    ("CALLBACK_SECRET", "callback_secret(inline)"),
    ("callback_secret", "callback_secret(inline)"),
    ("X-Callback-Token", "callback_secret(inline)"),
    ("X-Training-Callback", "callback_secret(inline)"),
    ("hmac.compare_digest", "shared_secret(compare_digest)"),
    ("get_jwt_identity", "jwt(inline)"),
    ("get_jwt(", "jwt(inline)"),
    ("verify_device_token", "device_token(inline)"),
    ("extract_device_id_unverified", "device_token(inline)"),
    ("X-Worker-Secret", "worker_secret(inline)"),
    ("WORKER_SECRET", "worker_secret(inline)"),
    ("X-Internal-Token", "internal_token(inline)"),
    ("INTERNAL_TOKEN", "internal_token(inline)"),
    ("X-API-Key", "api_key(inline)"),
    ("X-Enrollment-Token", "enrollment_token(inline)"),
    ("enrollment_token", "enrollment_token(inline)"),
    ("playback_token", "playback_token(inline)"),
    ("verify_playback_token", "playback_token(inline)"),
    ("require_superadmin()", "superadmin(inline)"),
    ("is_superadmin", "superadmin(check)"),
    ("has_permission(", "permission(inline)"),
    ("verify_andon_access", "ip_allowlist(inline)"),
    ("require_permission(", "permission(inline)"),
]

ENVELOPE_MARKERS = [
    ("success(", "success()"),
    ("error(", "error()"),
    ("jsonify(", "jsonify"),
    ("send_file(", "raw:file"),
    ("send_from_directory(", "raw:file"),
    ("stream_with_context", "raw:stream"),
    ("Response(", "raw:Response"),
    ("redirect(", "redirect"),
    ("make_response(", "raw:make_response"),
]

TENANT_MARKERS = [
    ("get_tenant_schema", "tenant_schema"),
    ("tenant_schema", "tenant_schema"),
    ("get_tenant_id", "tenant_id"),
    ("tenant_id", "tenant_id"),
    ("assumed_tenant", "assumed_context"),
    ("public.", "public.*"),
]


def _unwrap(func):
    """Segue ``__wrapped__`` (functools.wraps) até a view original."""
    seen = set()
    while hasattr(func, "__wrapped__") and id(func) not in seen:
        seen.add(id(func))
        func = func.__wrapped__
    return func


def _load_ast(path: Path, cache: dict[Path, ast.Module]) -> ast.Module:
    if path not in cache:
        cache[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return cache[path]


def _find_funcdef(tree: ast.Module, name: str, lineno: int):
    """Acha a FunctionDef pelo nome; desempata pela linha mais próxima."""
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            if best is None or abs(node.lineno - lineno) < abs(best.lineno - lineno):
                best = node
    return best


def _decorator_strings(node) -> list[str]:
    out = []
    for d in node.decorator_list:
        try:
            out.append(ast.unparse(d))
        except Exception:  # noqa: BLE001
            out.append("<unparseable>")
    return out


def _decorator_name(expr: str) -> str:
    # "jwt_required()" → "jwt_required"; "require_permission('x')" → "require_permission"
    # "limiter.limit('10/minute')" → "limiter.limit"
    return re.split(r"[(\s]", expr, maxsplit=1)[0]


def analyze_view(func, ast_cache: dict) -> dict:
    """Análise estática da view function: arquivo, linha, decorators, marcadores."""
    orig = _unwrap(func)
    info: dict = {
        "function": f"{orig.__module__}.{orig.__qualname__}",
        "file": None,
        "line": None,
        "decorators": [],
        "auth_decorators": [],
        "auth_body_markers": [],
        "auth_label": None,
        "envelope_markers": [],
        "tenant_markers": [],
        "rate_limited": False,
        "docstring": None,
        "delegated_to": [],
    }
    try:
        src_file = inspect.getsourcefile(orig)
        lines, lineno = inspect.getsourcelines(orig)
    except (OSError, TypeError):
        return info
    path = Path(src_file).resolve()
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        rel = path
    info["file"] = str(rel)
    info["line"] = lineno

    tree = _load_ast(path, ast_cache)
    node = _find_funcdef(tree, orig.__name__, lineno)
    if node is None:
        return info

    decs = _decorator_strings(node)
    info["decorators"] = [d for d in decs if not d.endswith(".route") and ".route(" not in d]
    body_src = "".join(lines)
    info["docstring"] = (ast.get_docstring(node) or "").strip().split("\n")[0][:160] or None

    auth_labels: list[str] = []
    for d in decs:
        name = _decorator_name(d).split(".")[-1]
        if name in AUTH_DECORATORS:
            label = AUTH_DECORATORS[name]
            if name == "jwt_required" and "optional=True" in d:
                label = "jwt(optional)"
            elif name in ("require_permission", "require_role", "require_module", "require_device_scope"):
                m = re.search(r"\(([^)]*)\)", d)
                label = f"{label}:{m.group(1).strip()}" if m else label
            info["auth_decorators"].append(d)
            auth_labels.append(label)
        if _decorator_name(d).endswith("limiter.limit") or _decorator_name(d) == "limit":
            info["rate_limited"] = True

    # Corpo SEM o docstring/decorators (linhas após o def)
    body_only = body_src
    # Delegação de 1 nível: `return handler(...)` → concatena o corpo do handler
    # (callbacks de training, p.ex., autenticam dentro do handler, não na view).
    delegated: list[str] = []
    for m in re.finditer(r"return\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", body_src):
        name = m.group(1)
        target = orig.__globals__.get(name)
        if (
            callable(target) and inspect.isfunction(target) and target is not orig
            and target.__module__.startswith("app.")
            and target.__module__ != "app.core.responses"
        ):
            try:
                delegated.append(f"{target.__module__}.{target.__qualname__}")
                body_only += "\n" + "".join(inspect.getsourcelines(_unwrap(target))[0])
            except (OSError, TypeError):
                pass
    info["delegated_to"] = sorted(set(delegated))
    for marker, label in AUTH_BODY_MARKERS:
        if marker in body_only and label not in info["auth_body_markers"]:
            info["auth_body_markers"].append(label)
    for marker, label in ENVELOPE_MARKERS:
        if marker in body_only and label not in info["envelope_markers"]:
            info["envelope_markers"].append(label)
    for marker, label in TENANT_MARKERS:
        if marker in body_only and label not in info["tenant_markers"]:
            info["tenant_markers"].append(label)

    if auth_labels:
        info["auth_label"] = "+".join(dict.fromkeys(auth_labels))
    elif info["auth_body_markers"]:
        info["auth_label"] = "+".join(info["auth_body_markers"])
    else:
        info["auth_label"] = "NONE(verificar)"
    return info


def build_inventory() -> tuple[list[dict], dict]:
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("JWT_SECRET_KEY", "inventory-only-not-a-secret-" + "x" * 32)
    os.environ.setdefault("SECRET_KEY", "inventory-only-not-a-secret-" + "y" * 32)
    sys.path.insert(0, str(API_DIR))
    os.chdir(API_DIR)

    from app import create_app  # noqa: PLC0415

    app = create_app("testing")
    ast_cache: dict = {}
    rows: list[dict] = []
    for rule in app.url_map.iter_rules():
        methods = sorted(m for m in (rule.methods or set()) if m not in ("HEAD", "OPTIONS"))
        endpoint = rule.endpoint
        blueprint = endpoint.rsplit(".", 1)[0] if "." in endpoint else "(app)"
        func = app.view_functions[endpoint]
        view = analyze_view(func, ast_cache)
        bp_obj = app.blueprints.get(blueprint)
        for method in methods:
            rows.append(
                {
                    "method": method,
                    "path": rule.rule,
                    "blueprint": blueprint,
                    "blueprint_import": bp_obj.import_name if bp_obj else None,
                    "url_prefix": bp_obj.url_prefix if bp_obj else None,
                    "endpoint": endpoint,
                    "path_params": sorted(rule.arguments),
                    **view,
                }
            )
    rows.sort(key=lambda r: (r["path"], r["method"]))

    summary = {
        "app_head": _git_head(),
        "total_rules": len(rows),
        "total_paths": len({r["path"] for r in rows}),
        "blueprints_registered": sorted(app.blueprints.keys()),
        "blueprints_without_rules": sorted(
            set(app.blueprints.keys()) - {r["blueprint"] for r in rows}
        ),
        "by_blueprint": dict(sorted(Counter(r["blueprint"] for r in rows).items())),
        "by_auth_label": dict(sorted(Counter(r["auth_label"] for r in rows).items())),
        "by_method": dict(sorted(Counter(r["method"] for r in rows).items())),
        "not_in_testing_url_map": [
            {"method": "GET", "path": "/api/v1/docs", "why": "Swagger UI só fora de TESTING (_configure_swagger)"},
            {"method": "GET", "path": "/api/v1/apispec.json", "why": "OpenAPI spec só fora de TESTING (_configure_swagger)"},
        ],
    }
    return rows, summary


def _git_head() -> str | None:
    try:
        import subprocess  # noqa: PLC0415

        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:  # noqa: BLE001
        return None


def write_markdown(rows: list[dict], summary: dict, out: Path) -> None:
    lines = [
        "# Inventário de endpoints — gerado por `tools/api_inventory.py`",
        "",
        f"- HEAD: `{summary['app_head']}`",
        f"- Regras (método×path): **{summary['total_rules']}** · paths únicos: **{summary['total_paths']}**",
        f"- Blueprints registrados: {len(summary['blueprints_registered'])}"
        + (f" · sem regra: {summary['blueprints_without_rules']}" if summary["blueprints_without_rules"] else ""),
        "",
        "> Colunas `auth`/`envelope`/`tenant` são marcadores estáticos do corpo da view (heurística).",
        "> A coluna verificada fica no mapa-contrato (`docs/migration/MAPA-MIGRACAO-FRONTEND.md`).",
        "",
        "| Método | Path | Blueprint | Função | Arquivo:linha | Auth (decorators/body) | Envelope | Tenant |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        fn = r["function"].rsplit(".", 1)[-1] if r["function"] else "?"
        loc = f"{r['file']}:{r['line']}" if r["file"] else "?"
        lines.append(
            f"| {r['method']} | `{r['path']}` | {r['blueprint']} | `{fn}` | `{loc}` | "
            f"{r['auth_label']} | {', '.join(r['envelope_markers']) or '—'} | "
            f"{', '.join(r['tenant_markers']) or '—'} |"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO_ROOT / "docs" / "migration" / "inventory"))
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    rows, summary = build_inventory()
    (out / "endpoints.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(rows, summary, out / "endpoints.md")
    print(f"rules={summary['total_rules']} paths={summary['total_paths']} blueprints={len(summary['blueprints_registered'])}")
    print(f"auth labels: {summary['by_auth_label']}")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
