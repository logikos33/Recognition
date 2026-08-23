#!/usr/bin/env python3
"""Monta o mapa-contrato da migração do frontend a partir dos inventários.

Subcomandos
-----------
    inputs   — gera ``docs/migration/inventory/domains/<dominio>.input.json`` (a lista de
               endpoints de cada domínio, com baseline estática + evidências de consumo)
               para a leitura linha a linha por domínio.
    build    — lê ``domains/<dominio>.json`` (saída verificada por domínio) + inventários e
               escreve ``docs/migration/MAPA-MIGRACAO-FRONTEND.md`` (tabela por domínio) e
               ``docs/migration/inventory/map_summary.json`` (contagens).
    check    — consistência: rótulo do domínio × evidência do scanner (FRONT-ATUAL sem chamada viva,
               chamada viva sem FRONT-ATUAL), endpoints faltando/duplicados, rótulos inválidos.
    design   — escreve ``docs/migration/LISTA-PARA-O-DESIGN.md`` (linguagem de produto) a partir
               de ``design_needs`` de cada domínio, das seções "(d)" dos fluxos do front e dos
               endpoints GAP-DE-PRODUTO (anexo de rastreabilidade).

O mapa nunca é editado à mão: corrigiu algo → corrige o JSON do domínio e roda ``build``.

Uso
---
    python3 tools/build_migration_map.py inputs
    python3 tools/build_migration_map.py build
    python3 tools/build_migration_map.py design
    python3 tools/build_migration_map.py check
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INV = REPO_ROOT / "docs" / "migration" / "inventory"
DOMAINS_DIR = INV / "domains"
MAP_MD = REPO_ROOT / "docs" / "migration" / "MAPA-MIGRACAO-FRONTEND.md"
DESIGN_MD = REPO_ROOT / "docs" / "migration" / "LISTA-PARA-O-DESIGN.md"

# blueprint → domínio (ordem = ordem das seções no mapa)
DOMAINS: "OrderedDict[str, dict]" = OrderedDict(
    [
        ("auth-identity", {
            "title": "Autenticação, identidade, permissões e contexto",
            "blueprints": ["auth", "roles", "admin_permissions", "my_permissions",
                           "admin_impersonation", "impersonation", "admin_tenant_context"],
        }),
        ("admin-core-a", {
            "title": "Admin da plataforma (A) — tenants, usuários, planos, flags",
            "blueprints": ["admin"], "split": ("a", 2),
        }),
        ("admin-core-b", {
            "title": "Admin da plataforma (B) — tickets, workers, auditoria, inventário, anúncios",
            "blueprints": ["admin", "client_announcements"], "split": ("b", 2),
        }),
        ("admin-aux", {
            "title": "Admin auxiliar — branding, integrações, versões, observabilidade, consoles de teste/demo",
            "blueprints": ["admin_branding", "tenant_branding", "branding", "admin_integrations",
                           "admin_introspection", "admin_observability", "admin_versions",
                           "admin_test_console", "test_console", "demo_events", "demo_videos"],
        }),
        ("cameras-streams", {
            "title": "Câmeras, streams/live view e gravadores",
            "blueprints": ["cameras", "cameras_v1", "streams", "recorders"],
        }),
        ("training", {
            "title": "Treinamento, anotação, propagação e busca",
            "blueprints": ["training"],
        }),
        ("models-datasets-rules", {
            "title": "Modelos (rollout), datasets, cenários, módulos e regras",
            "blueprints": ["datasets", "models_rollout", "scenarios", "modules", "rules"],
        }),
        ("quality", {
            "title": "Módulo Qualidade (inspeções, gate, estações, relatórios, treino)",
            "blueprints": ["quality"],
        }),
        ("edge-fleet", {
            "title": "Edge / frota — enrollment, heartbeat, comandos, eventos, monitoring",
            "blueprints": ["edge", "edge_commands", "edge_events", "site_gateways", "devices",
                           "monitoring", "dashboard_edge"],
        }),
        ("events-alerts-media", {
            "title": "Eventos, alertas, notificações, feedback, verificação, vídeos, storage, retenção",
            "blueprints": ["alerts", "events", "notifications", "feedback", "verification",
                           "videos", "storage", "retention"],
        }),
        ("ops-dashboard-misc", {
            "title": "Dashboard, relatórios, contagem, operações, abastecimento, chat, monofatura, health",
            "blueprints": ["dashboard", "reports", "counting", "counting_v1", "operations",
                           "fueling", "chat", "monofatura", "health", "(app)"],
        }),
    ]
)

LABELS = ("FRONT-ATUAL", "BACKEND-ONLY", "ÓRFÃO", "GAP-DE-PRODUTO")


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _rule_key(r: dict) -> str:
    return f"{r['method']} {r['path']}"


def _assign_domain(rows: list[dict]) -> dict[str, list[dict]]:
    """Distribui as regras pelos domínios; blueprint 'admin' é partido em 2 metades por path."""
    by_dom: dict[str, list[dict]] = defaultdict(list)
    admin_rows = sorted([r for r in rows if r["blueprint"] == "admin"], key=lambda r: (r["path"], r["method"]))
    half = (len(admin_rows) + 1) // 2
    admin_split = {"a": admin_rows[:half], "b": admin_rows[half:]}
    for dom, spec in DOMAINS.items():
        for r in rows:
            if r["blueprint"] == "admin":
                continue
            if r["blueprint"] in spec["blueprints"]:
                by_dom[dom].append(r)
        if "split" in spec:
            by_dom[dom].extend(admin_split[spec["split"][0]])
    assigned = {id(r) for rs in by_dom.values() for r in rs}
    leftovers = [r for r in rows if id(r) not in assigned]
    if leftovers:
        by_dom["_sem-dominio"] = leftovers
    for dom in by_dom:
        by_dom[dom].sort(key=lambda r: (r["path"], r["method"]))
    return by_dom


def cmd_inputs() -> int:
    rows = _load(INV / "endpoints.json")
    cls = {f"{c['method']} {c['path']}": c for c in _load(INV / "classification.json")}
    by_dom = _assign_domain(rows)
    DOMAINS_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for dom, rs in by_dom.items():
        items = []
        for r in rs:
            c = cls.get(_rule_key(r), {})
            items.append({
                "method": r["method"], "path": r["path"], "endpoint": r["endpoint"],
                "blueprint": r["blueprint"], "file": r["file"], "line": r["line"],
                "function": r["function"], "decorators": r["decorators"],
                "auth_static": r["auth_label"], "envelope_static": r["envelope_markers"],
                "tenant_static": r["tenant_markers"], "delegated_to": r["delegated_to"],
                "rate_limited": r["rate_limited"], "docstring": r["docstring"],
                "label_preliminar": c.get("label_preliminar"),
                "frontend_evidence": c.get("frontend_evidence", []),
                "other_evidence": [o for o in c.get("other_evidence", []) if o.get("kind") == "code"],
            })
        spec = DOMAINS.get(dom, {"title": dom})
        (DOMAINS_DIR / f"{dom}.input.json").write_text(json.dumps({
            "domain": dom, "title": spec["title"], "endpoint_count": len(items), "endpoints": items,
        }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        total += len(items)
        print(f"{dom:24} {len(items):4d} endpoints")
    print(f"total={total} (inventário={len(rows)})")
    return 0 if total == len(rows) else 1


# ----------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------

def _md_escape(s) -> str:
    if s is None:
        return "—"
    return str(s).replace("|", "\\|").replace("\n", " ")


def cmd_build() -> int:
    rows = _load(INV / "endpoints.json")
    summary = _load(INV / "summary.json")
    consumers = _load(INV / "consumers.json")
    db = _load(INV / "db_schema_dev.json") if (INV / "db_schema_dev.json").exists() else None
    by_dom = _assign_domain(rows)

    verified: dict[str, dict] = {}      # "METHOD path" → registro verificado
    dom_meta: dict[str, dict] = {}
    missing_domains = []
    for dom in by_dom:
        p = DOMAINS_DIR / f"{dom}.json"
        if not p.exists():
            missing_domains.append(dom)
            continue
        d = _load(p)
        dom_meta[dom] = d
        for e in d.get("endpoints", []):
            verified[f"{e['method']} {e['path']}"] = e

    counts = Counter()
    per_dom_counts: dict[str, Counter] = {}
    unverified = []
    out = []
    out.append("# MAPA-CONTRATO — Migração do Frontend (backend 100% mapeado)\n")
    out.append(f"> Gerado por `tools/build_migration_map.py build` a partir de `docs/migration/inventory/` "
               f"(HEAD `{summary.get('app_head')}`). **Não edite à mão** — corrija o JSON do domínio e regere.\n")
    out.append("> Fonte: código real de `origin/develop` (url_map via `create_app()`), consumo real em "
               "`apps/frontend/src` (matcher do Flask) e banco DEV real (snapshot read-only). "
               "Zero mudança de comportamento.\n")
    out.append("\n## Regra de fechamento\n")
    out.append("**A migração só fecha quando a coluna `NOVO FRONT` estiver 100% resolvida** "
               "(`cobre` / `não cobre` / `n.a.`) para TODOS os endpoints `FRONT-ATUAL` e `GAP-DE-PRODUTO`, "
               "TODOS os eventos SocketIO e TODAS as dependências de ambiente — e quando nenhum `não cobre` "
               "em `FRONT-ATUAL` restar sem decisão consciente registrada (com dono e data). "
               "`BACKEND-ONLY` e `ÓRFÃO` entram como `n.a.` por padrão, mas não podem quebrar.\n")
    out.append("\n## Legenda\n")
    out.append("- **Etiqueta**: `FRONT-ATUAL` (front de hoje consome — evidência arquivo:linha) · "
               "`BACKEND-ONLY` (edge/worker/callback/infra — novo front não toca) · `ÓRFÃO` (ninguém chama) · "
               "`GAP-DE-PRODUTO` (back suporta, front não usa — avaliar no design)\n")
    out.append("- **Auth**: `jwt` (Bearer, claims tenant_id/tenant_schema/role/modules_enabled) · `superadmin` · "
               "`permission:<x>` · `device_scope:<x>` (JWT RS256 do device) · `enrollment_token` · "
               "`callback_secret` · `playback_token` · `public`\n")
    out.append("- **Tenant**: `public.tenant_id` (tabela pública com coluna tenant_id) · `tenant_schema` "
               "(search_path no schema do tenant) · `global` (plataforma/superadmin) · `n.a.`\n")
    out.append("- **Envelope**: `success/error` = `{success, message, data}` / `{success:false, error}`; "
               "exceções sinalizadas (`jsonify`, `raw`, CSV, binário, redirect)\n")
    out.append("- **NOVO FRONT**: coluna a preencher cruzando com o design — `cobre` / `não cobre` / `n.a.`\n")

    for dom, rs in by_dom.items():
        spec = DOMAINS.get(dom, {"title": dom})
        meta = dom_meta.get(dom, {})
        per_dom_counts[dom] = Counter()
        out.append(f"\n---\n\n## {spec['title']}\n")
        out.append(f"_Domínio `{dom}` · {len(rs)} endpoints · blueprints: {', '.join(spec.get('blueprints', []))}_\n")
        if meta.get("overview"):
            out.append(f"\n{meta['overview']}\n")
        out.append("\n| Método | Path | Auth | Tenant | Envelope | Request | Response (data) | Tabelas | Etiqueta | Evidência | Notas de comportamento | NOVO FRONT |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rs:
            k = _rule_key(r)
            v = verified.get(k)
            if v is None:
                unverified.append(k)
                label = r.get("label_preliminar") or "?"
                auth = r["auth_label"]; tenant = ", ".join(r["tenant_markers"]) or "—"
                env = ", ".join(r["envelope_markers"]) or "—"
                req = resp = tables = notes = "(não verificado)"
                evid = "—"
            else:
                label = v.get("label") or "?"
                auth = v.get("auth") or r["auth_label"]
                tenant = v.get("tenant") or "—"
                env = v.get("envelope") or "—"
                req = v.get("request") or "—"
                resp = v.get("response") or "—"
                tables = ", ".join(v.get("tables", [])) or "—"
                notes = v.get("behavior_notes") or "—"
                ev = v.get("evidence") or []
                evid = "; ".join(ev) if ev else "—"
            counts[label] += 1
            per_dom_counts[dom][label] += 1
            loc = f"{r['file']}:{r['line']}"
            out.append(
                f"| {r['method']} | `{r['path']}`<br><sub>`{loc}`</sub> | {_md_escape(auth)} | {_md_escape(tenant)} | "
                f"{_md_escape(env)} | {_md_escape(req)} | {_md_escape(resp)} | {_md_escape(tables)} | "
                f"**{_md_escape(label)}** | {_md_escape(evid)} | {_md_escape(notes)} | |"
            )
        if meta.get("flows"):
            out.append("\n**Fluxos / contrato comportamental (além do REST):**\n")
            for f in meta["flows"]:
                out.append(f"- **{_md_escape(f.get('name'))}** — {_md_escape(f.get('description'))}"
                           + (f" _(endpoints: {', '.join('`'+e+'`' for e in f.get('endpoints', []))})_" if f.get("endpoints") else ""))
        if meta.get("tables_by_scope"):
            tb = meta["tables_by_scope"]
            out.append("\n**Banco (conferido contra DEV):** "
                       f"public: {', '.join('`'+t+'`' for t in tb.get('public', [])) or '—'} · "
                       f"tenant_schema: {', '.join('`'+t+'`' for t in tb.get('tenant_schema', [])) or '—'}")
            if tb.get("not_in_dev"):
                out.append(f"  · ⚠️ referenciadas no código e AUSENTES no DEV: {', '.join('`'+t+'`' for t in tb['not_in_dev'])}")
        if meta.get("findings"):
            out.append("\n**Achados:**\n")
            for f in meta["findings"]:
                out.append(f"- [{_md_escape(f.get('severity'))}] {_md_escape(f.get('text'))}")
        c = per_dom_counts[dom]
        out.append("\n_Contagem do domínio: " + " · ".join(f"{k}: {c[k]}" for k in LABELS if c[k]) +
                   (f" · não verificado: {c.get('?', 0)}" if c.get("?") else "") + "_")

    # Seções transversais (se existirem)
    for extra in ("socketio-env", "frontend-flows-pages", "frontend-flows-modules"):
        p = DOMAINS_DIR / f"{extra}.md"
        if p.exists():
            out.append(f"\n---\n\n{p.read_text(encoding='utf-8').strip()}\n")

    # Resumo
    out.insert(3, "\n## Resumo\n")
    resumo = [
        f"- Endpoints (método×path): **{len(rows)}** em {len(summary['blueprints_registered'])} blueprints · "
        f"paths únicos: {summary['total_paths']}",
        "- Etiquetas: " + " · ".join(f"**{k}**: {counts[k]}" for k in LABELS) +
        (f" · não verificado: {counts.get('?', 0)}" if counts.get("?") else ""),
        f"- Chamadas do front extraídas: {consumers['summary']['frontend_calls_total']} "
        f"(casadas {consumers['summary']['frontend_calls_matched']}, sem regra {consumers['summary']['frontend_calls_unmatched']}, "
        f"dinâmicas {consumers['summary']['frontend_calls_dynamic']})",
        f"- Sockets do front: {consumers['summary']['frontend_sockets']} subscrições · env do front: "
        f"{', '.join(consumers['summary']['frontend_env_vars'].keys())}",
    ]
    if db:
        resumo.append(f"- Banco DEV: {sum(db['counts'].values())} tabelas em {len(db['counts'])} schemas "
                      f"({', '.join(f'{s}={n}' for s, n in db['counts'].items())})")
    if missing_domains:
        resumo.append(f"- ⚠️ domínios sem saída verificada: {missing_domains}")
    out.insert(4, "\n".join(resumo) + "\n")

    MAP_MD.parent.mkdir(parents=True, exist_ok=True)
    MAP_MD.write_text("\n".join(out) + "\n", encoding="utf-8")
    (INV / "map_summary.json").write_text(json.dumps({
        "head": summary.get("app_head"),
        "endpoints": len(rows),
        "labels": dict(counts),
        "per_domain": {d: dict(c) for d, c in per_dom_counts.items()},
        "unverified": unverified,
        "missing_domains": missing_domains,
    }, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"labels={dict(counts)} unverified={len(unverified)} missing_domains={missing_domains}")
    print(f"written: {MAP_MD}")
    return 0


# ----------------------------------------------------------------------------
# design
# ----------------------------------------------------------------------------

def _extract_section(md: str, heading_prefix: str) -> str:
    """Devolve o corpo da primeira seção cujo heading começa com `heading_prefix` (até o próximo heading de mesmo nível)."""
    lines = md.splitlines()
    out, level, on = [], None, False
    for ln in lines:
        if ln.startswith("#"):
            lvl = len(ln) - len(ln.lstrip("#"))
            title = ln.lstrip("#").strip()
            if on and lvl <= level:
                break
            if not on and title.startswith(heading_prefix):
                on, level = True, lvl
                continue
        if on:
            out.append(ln)
    return "\n".join(out).strip()


def cmd_design() -> int:
    rows = _load(INV / "endpoints.json")
    summary = _load(INV / "summary.json")
    by_dom = _assign_domain(rows)
    out = [
        "# LISTA PARA O DESIGN — o que o backend exige que o novo front construa ou melhore",
        "",
        f"> Gerado por `tools/build_migration_map.py design` (HEAD `{summary.get('app_head')}`) a partir dos JSONs verificados por domínio "
        "e dos fluxos do front atual. Linguagem de **produto** (telas/fluxos), não de rota. O anexo no fim dá a rastreabilidade "
        "rota→item para quem for implementar. **Não edite à mão** — corrija `docs/migration/inventory/domains/*.json` e regere.",
        "",
        "Como usar: cada item é uma tela/fluxo que o backend já suporta (ou exige) e que o front atual não cobre, cobre mal, ou cobre com bug. "
        "O design decide `cobre` / `não cobre` por item; a decisão volta para a coluna **NOVO FRONT** do mapa-contrato. "
        "Itens marcados **[pré-requisito backend]** dependem de correção no servidor antes de o front conseguir entregar.",
        "",
        "## 0. Transversal (vale para todas as telas)",
        "",
    ]
    # transversais: seção (d) dos fluxos + "o que o novo front precisa implementar" do socket
    for fname, title in (("frontend-flows-pages.md", "Páginas (pages/)"), ("frontend-flows-modules.md", "Módulos (modules/)"), ("socketio-env.md", "Tempo real / ambiente")):
        p = DOMAINS_DIR / fname
        if not p.exists():
            continue
        md = p.read_text(encoding="utf-8")
        body = _extract_section(md, "(d)") or _extract_section(md, "O que o novo front precisa implementar") or _extract_section(md, "CHECKLIST")
        if body:
            out.append(f"### {title}")
            out.append("")
            out.append(body)
            out.append("")
    n_total = 0
    annex = []
    for i, (dom, rs) in enumerate(by_dom.items(), start=1):
        spec = DOMAINS.get(dom, {"title": dom})
        p = DOMAINS_DIR / f"{dom}.json"
        if not p.exists():
            continue
        d = _load(p)
        needs = d.get("design_needs", [])
        gaps = [e for e in d.get("endpoints", []) if e.get("label") == "GAP-DE-PRODUTO"]
        out.append(f"## {i}. {spec['title']}")
        out.append("")
        if d.get("overview"):
            out.append(f"_{d['overview'].strip()}_")
            out.append("")
        if not needs:
            out.append("_(nenhum item de design registrado — ver achados no mapa)_")
        for j, item in enumerate(needs, start=1):
            n_total += 1
            out.append(f"{j}. {item}")
        out.append("")
        out.append(f"_GAP-DE-PRODUTO neste domínio: {len(gaps)} endpoint(s) sem UI — ver anexo A.{i}._")
        out.append("")
        annex.append((i, spec["title"], gaps))
    out.append("---")
    out.append("")
    out.append("## Anexo A — Rastreabilidade: endpoints GAP-DE-PRODUTO por domínio (para quem implementa)")
    out.append("")
    for i, title, gaps in annex:
        out.append(f"### A.{i} {title} ({len(gaps)})")
        out.append("")
        if not gaps:
            out.append("—")
            out.append("")
            continue
        out.append("| Método | Path | O que o back oferece (resposta) | Por que é gap |")
        out.append("|---|---|---|---|")
        for g in gaps:
            out.append(f"| {g['method']} | `{g['path']}` | {_md_escape(g.get('response'))} | {_md_escape(g.get('label_reason'))} |")
        out.append("")
    DESIGN_MD.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"design items={n_total} gaps={sum(len(g) for _,_,g in annex)} -> {DESIGN_MD}")
    return 0


# ----------------------------------------------------------------------------
# check
# ----------------------------------------------------------------------------

def cmd_check() -> int:
    rows = _load(INV / "endpoints.json")
    cls = {f"{c['method']} {c['path']}": c for c in _load(INV / "classification.json")}
    by_dom = _assign_domain(rows)
    problems = []
    for dom, rs in by_dom.items():
        p = DOMAINS_DIR / f"{dom}.json"
        if not p.exists():
            problems.append(f"[{dom}] saída ausente")
            continue
        d = _load(p)
        seen = Counter(f"{e['method']} {e['path']}" for e in d.get("endpoints", []))
        expected = {_rule_key(r) for r in rs}
        for k, n in seen.items():
            if n > 1:
                problems.append(f"[{dom}] duplicado na saída: {k} (x{n})")
            if k not in expected:
                problems.append(f"[{dom}] endpoint fora do input: {k}")
        for k in sorted(expected - set(seen)):
            problems.append(f"[{dom}] endpoint do input ausente na saída: {k}")
        for e in d.get("endpoints", []):
            k = f"{e['method']} {e['path']}"
            lab = e.get("label")
            if lab not in LABELS:
                problems.append(f"[{dom}] rótulo inválido em {k}: {lab!r}")
                continue
            c = cls.get(k, {})
            live = c.get("frontend_evidence", [])
            dead = c.get("frontend_dead_evidence", [])
            if live and lab != "FRONT-ATUAL":
                where = "; ".join(f"{x['file']}:{x['line']}" for x in live[:3])
                problems.append(f"[{dom}] scanner vê chamada VIVA mas rótulo={lab}: {k} ← {where} | motivo: {e.get('label_reason','')[:120]}")
            if not live and lab == "FRONT-ATUAL":
                ev = "; ".join(e.get("evidence", [])[:3])
                hint = " (só código morto no scanner)" if dead else ""
                problems.append(f"[{dom}] rótulo FRONT-ATUAL sem chamada viva no scanner{hint}: {k} | evidência citada: {ev}")
    for pr in problems:
        print(pr)
    print(f"\n{len(problems)} inconsistência(s)")
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["inputs", "build", "design", "check"])
    args = ap.parse_args()
    return {"inputs": cmd_inputs, "build": cmd_build, "design": cmd_design, "check": cmd_check}[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())
