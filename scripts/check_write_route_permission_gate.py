"""
Write-route permission gate — AST scan: toda rota de ESCRITA (POST/PUT/PATCH/
DELETE) registrada sob services/api/app/api/ precisa de um gate de permissão
EXPLÍCITO, por um dos três mecanismos REAIS deste repo:
  1. decorator  — GATE_DECORATORS (require_permission/require_admin/...)
  2. inline v2  — INLINE_GATE_CALLS, `has_permission("chave")` (WS7, coberto
                  por tests/security/test_permission_gate_parity.py)
  3. inline legado — comparar get_role() contra um literal/coleção de roles
                  (ROLE_COMPARE_OPS) — pré-WS7, ainda usado em vários
                  handlers (ex.: pin_model_version, create_command); ignorar
                  este padrão faria o gate acusar como "aberta" uma rota que
                  JÁ foi corrigida (demo_seed — ver "achado #5" no código).
Zero um dos três → violação.

Motivação (P0 real, achado nesta rodada de mutirão): POST /api/training/jobs
tinha só `@limiter.limit(...)` + `@jwt_required()` — zero gate de permissão.
Qualquer usuário autenticado, de qualquer papel, disparava treino real (GPU
paga). `@jwt_required()` só prova QUEM é o usuário — nunca O QUE ele pode
fazer. Esse buraco só foi achado varrendo manualmente; este script vira essa
varredura numa regra permanente de CI.

Por que AST e não regex: decorator pode vir em qualquer ordem relativa aos
outros (`@jwt_required()` acima ou abaixo do gate), com ou sem argumento
(`@require_admin` vs `@require_permission("x")`), e o handler real de uma
rota registrada via `Blueprint.add_url_rule(view_func=...)` (em vez de
`@bp.route(...)`) mora em OUTRO arquivo — ex.: cameras/routes.py aponta para
cameras/probe_handler.py. Regex não resolve nem indireção de import nem
ordem de decorator; texto que "parece" ter o decorator certo na linha errada
já enganou uma régua desta mesma rodada (classe removida, regex passou
verde). AST não erra por posição nem por formatação de linha.

Catraca (decisão do Vitor): há ~70 rotas de escrita PRÉ-EXISTENTES sem gate
(débito real, não mascarado na ALLOWLIST). Em vez de reprovar por elas
existirem, o script congela a lista em BASELINE_FILE
(scripts/write_route_gate_baseline.txt) e só reprova quando ela CRESCE (rota
nova sem gate) ou fica DESATUALIZADA PARA MENOS (rota do baseline já corrigida
no código, mas a linha continua lá — a catraca tem de apertar). Ver
check_ratchet()/load_baseline().

Uso:
  python scripts/check_write_route_permission_gate.py               # falha se violação
  python scripts/check_write_route_permission_gate.py --report-only # só imprime, não falha
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api" / "app" / "api"
# "app.foo.bar" resolve para services/api/app/foo/bar.py — pai de "app" é services/api.
APP_PKG_PARENT = REPO_ROOT / "services" / "api"

WRITE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Decorators que de fato BLOQUEIAM por autorização (não apenas autenticação).
# ⛔ NUNCA incluir `admin_required` (app/core/auth.py) aqui: está documentado
# como DEPRECATED — só seta kwargs['require_admin']=True e delega ao service
# chamado; não bloqueia ninguém sozinho. Incluí-lo aqui criaria um falso
# negativo (rota "parece" gated e não está).
GATE_DECORATORS: frozenset[str] = frozenset({
    "require_permission",         # app/core/tenant.py — chave do registry canônico (WS7)
    "require_admin",              # app/core/tenant.py — role in (admin, superadmin)
    "require_superadmin",         # app/core/tenant.py — role == superadmin
    "require_superadmin_or_404",  # app/core/tenant_context.py — idem, 404 (C-01, não vaza existência)
    "require_training_role",      # app/core/auth.py — registry training:write/approve (ADR-0037)
    "require_device_scope",       # app/core/device_auth.py — autorização de DEVICE (edge, não role de usuário)
})

# Chamada inline sancionada — mesmo mecanismo de GATE_DECORATORS, sem
# decorator. Padrão real e testado (tests/security/test_permission_gate_parity.py)
# usado em ~40 rotas: edge/routes.py, notifications/routes.py, devices/routes.py,
# site_gateways/routes.py, cameras/*_handler.py, retention/routes.py.
INLINE_GATE_CALLS: frozenset[str] = frozenset({"has_permission"})

# Comparação (In/NotIn/Eq/NotEq/Is/IsNot) contra get_role() ou uma variável
# atribuída direto de get_role() — padrão legado pré-WS7, ainda usado em
# vários handlers (ex.: pin_model_version, create_command, demo_seed —
# este último é uma vulnerabilidade REAL já corrigida, ver comentário
# "achado #5" em quality/routes.py; não reconhecer este padrão faria o gate
# reportar como aberta uma rota que já foi corrigida). Só conta se o valor
# participa de uma comparação — `actor_role = get_role()` passado só para
# log/auditoria (sem comparar) não restringe ninguém e não deve contar.
ROLE_COMPARE_OPS: tuple[type, ...] = (
    ast.In, ast.NotIn, ast.Eq, ast.NotEq, ast.Is, ast.IsNot,
)

# Limite de profundidade ao seguir chamadas dentro do handler (rotas finas
# que só fazem `return xxx_handler()` — o gate real mora no handler chamado,
# possivelmente em outro arquivo). Cadeias reais neste repo têm no máximo 1-2
# saltos; 4 é folga generosa sem risco de explosão (funções são pequenas).
MAX_CALL_DEPTH = 4

# Allowlist de rotas de ESCRITA sem gate de permissão — cada entrada com
# motivo. Chave: "{arquivo_de_registro}::{handler}::{método}". ⛔ Entrada sem
# motivo real (ou motivo "pra passar o teste") é o mesmo buraco com outro
# nome — não adicione uma entrada aqui sem justificar por que a rota é
# publicamente aberta OU autentica por um mecanismo que não é role de
# usuário (device/HMAC/token one-time).
ALLOWLIST: dict[str, str] = {
    # --- Autenticação: pré-condição para ter qualquer permissão ---
    "services/api/app/api/v1/auth/routes.py::register::POST":
        "Cadastro de usuário — anônimo por natureza, é o próprio ponto de entrada.",
    "services/api/app/api/v1/auth/routes.py::login::POST":
        "Login — anônimo por natureza, emite o JWT que os demais gates leem.",
    "services/api/app/api/v1/auth/routes.py::forgot_password::POST":
        "Solicitação de reset de senha (ADR-0042) — anônimo por design, e-mail é o gate.",
    "services/api/app/api/v1/auth/routes.py::reset_password::POST":
        "Conclusão de reset de senha (ADR-0042) — token de uso único no corpo é o gate, não role.",

    # --- Device auth (edge): autoriza o DEVICE, não um usuário com role ---
    "services/api/app/api/v1/edge/routes.py::ingest_heartbeat::POST":
        "Heartbeat do edge-sync-agent — autentica por RS256 device auth inline "
        "(extract_device_id_unverified + verificação de assinatura), não JWT de usuário.",
    "services/api/app/api/v1/edge/routes.py::enroll_device::POST":
        "Enrollment de device edge (ADR-0019) — token one-time de enrollment é o gate, "
        "verificado inline; o device ainda não tem identidade para ter um role.",

    # --- Callback interno GPU→API: autentica por HMAC, não por role de usuário ---
    "services/api/app/api/v1/training/routes.py::training_progress_callback::POST":
        "Callback do worker de treino remoto (RunPod/Vast) — pod não tem JWT de "
        "usuário; autentica via X-Callback-Token (hmac.compare_digest contra "
        "training_jobs.callback_token), ver comentário acima da rota.",
    "services/api/app/api/v1/training/routes.py::propagation_callback::POST":
        "Mesmo padrão de training_progress_callback (X-Callback-Token/hmac) — "
        "callback do worker de propagação (DINOv2+SAM), ver comentário acima da rota.",
    "services/api/app/api/v1/training/routes.py::search_callback::POST":
        "Mesmo padrão de training_progress_callback (X-Callback-Token/hmac) — "
        "callback do worker de busca por conteúdo (OWLv2), ver comentário acima da rota.",

    # --- Worker on-premise: autentica por secret de header, não JWT/role ---
    "services/api/app/api/v1/admin/routes.py::worker_heartbeat::POST":
        "Heartbeat do worker on-premise — autentica via X-Worker-Secret "
        "(comparado a current_app.config['WORKER_SECRET']), não JWT de usuário.",
}


@dataclass
class ModuleInfo:
    """Metadados de um arquivo .py já parseado: funções top-level + imports."""

    file: Path
    tree: ast.Module
    funcs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(default_factory=dict)
    # nome local usado no arquivo -> (arquivo resolvido ou None, nome original no destino)
    imports: dict[str, tuple[Path | None, str]] = field(default_factory=dict)


@dataclass
class Violation:
    file: Path
    handler: str
    handler_file: Path
    method: str
    reason: str


_MODULE_CACHE: dict[Path, ModuleInfo | None] = {}


def _module_to_path(pkg_root: Path, dotted: str) -> Path | None:
    parts = dotted.split(".")
    as_file = pkg_root.joinpath(*parts).with_suffix(".py")
    if as_file.exists():
        return as_file
    as_pkg = pkg_root.joinpath(*parts, "__init__.py")
    if as_pkg.exists():
        return as_pkg
    return None


def _resolve_import_target(current_file: Path, node: ast.ImportFrom) -> Path | None:
    if node.level and node.level > 0:
        base = current_file.parent
        for _ in range(node.level - 1):
            base = base.parent
        if node.module:
            return _module_to_path(base, node.module)
        init = base / "__init__.py"
        return init if init.exists() else None

    if node.module and node.module.startswith("app."):
        return _module_to_path(APP_PKG_PARENT, node.module)
    if node.module == "app":
        return _module_to_path(APP_PKG_PARENT, node.module)
    return None  # import externo (flask, stdlib, etc.) — nada nosso a seguir


def _get_module_info(file: Path) -> ModuleInfo | None:
    file = file.resolve()
    if file in _MODULE_CACHE:
        return _MODULE_CACHE[file]

    if not file.exists():
        _MODULE_CACHE[file] = None
        return None

    try:
        tree = ast.parse(file.read_text(), filename=str(file))
    except SyntaxError:
        _MODULE_CACHE[file] = None
        return None

    info = ModuleInfo(file=file, tree=tree)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.funcs[node.name] = node
        elif isinstance(node, ast.ImportFrom):
            target = _resolve_import_target(file, node)
            for alias in node.names:
                local_name = alias.asname or alias.name
                info.imports[local_name] = (target, alias.name)

    _MODULE_CACHE[file] = info
    return info


def _decorator_root_name(dec: ast.expr) -> str | None:
    if isinstance(dec, ast.Call):
        return _decorator_root_name(dec.func)
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Name):
        return dec.id
    return None


def _call_root_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _is_get_role_call(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Call) and _call_root_name(expr.func) == "get_role"


def _has_inline_role_check(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Padrão legado pré-WS7: `role = get_role(); if role not in (...): ...`
    ou direto `if get_role() not in _ADMIN_ROLES: ...`. Ver ROLE_COMPARE_OPS."""
    role_vars: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Assign) and _is_get_role_call(child.value):
            for tgt in child.targets:
                if isinstance(tgt, ast.Name):
                    role_vars.add(tgt.id)

    def _is_role_expr(expr: ast.expr) -> bool:
        return _is_get_role_call(expr) or (isinstance(expr, ast.Name) and expr.id in role_vars)

    for child in ast.walk(node):
        if not isinstance(child, ast.Compare):
            continue
        if not any(isinstance(op, ROLE_COMPARE_OPS) for op in child.ops):
            continue
        if any(_is_role_expr(c) for c in (child.left, *child.comparators)):
            return True
    return False


def _resolve_callable(
    name: str, info: ModuleInfo
) -> tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef] | None:
    if name in info.funcs:
        return info.file, info.funcs[name]
    if name in info.imports:
        target_file, orig_name = info.imports[name]
        if target_file is None:
            return None
        target_info = _get_module_info(target_file)
        if target_info and orig_name in target_info.funcs:
            return target_info.file, target_info.funcs[orig_name]
    return None


def _is_route_gated(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file: Path,
    visited: set[tuple[str, str]] | None = None,
    depth: int = 0,
) -> bool:
    """True se `node` (ou algo que ele chama, até MAX_CALL_DEPTH) tem gate."""
    if visited is None:
        visited = set()
    key = (str(file), node.name)
    if key in visited or depth > MAX_CALL_DEPTH:
        return False
    visited.add(key)

    decorator_names = {_decorator_root_name(d) for d in node.decorator_list}
    if decorator_names & GATE_DECORATORS:
        return True
    if _has_inline_role_check(node):
        return True

    info = _get_module_info(file)
    if info is None:
        return False

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_root_name(child.func)
        if name is None:
            continue
        if name in INLINE_GATE_CALLS:
            return True
        target = _resolve_callable(name, info)
        if target is not None:
            target_file, target_node = target
            if _is_route_gated(target_node, target_file, visited, depth + 1):
                return True
    return False


def _methods_from_call(call: ast.Call) -> set[str] | None:
    for kw in call.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
            return {
                elt.value
                for elt in kw.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
    return None


# Atalhos de método do Flask 2.x (`@bp.post(...)` == `@bp.route(..., methods=["POST"])`).
_SHORTHAND_METHODS: frozenset[str] = frozenset({"get", "post", "put", "patch", "delete"})


def _find_route_decorator_registrations(
    tree: ast.Module,
) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, set[str]]]:
    """`@bp.route(url, methods=[...])` OU o atalho `@bp.post(url)` (mesma
    coisa, sem precisar do kwarg methods=) direto acima de uma função
    top-level. admin/integration_routes.py e admin/test_console_routes.py
    usam só o atalho — perdê-lo deixaria essas rotas invisíveis ao scan
    (pior que um falso positivo: um "tudo limpo" que não viu a rota)."""
    found = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            attr = dec.func.attr
            if attr == "route":
                methods = _methods_from_call(dec)
            elif attr in _SHORTHAND_METHODS:
                methods = _methods_from_call(dec) or {attr.upper()}
            else:
                continue
            if methods:
                found.append((node, methods))
    return found


def _find_add_url_rule_registrations(
    tree: ast.Module,
) -> list[tuple[str, set[str]]]:
    """`bp.add_url_rule(url, view_func=name, methods=[...])` em qualquer lugar do módulo."""
    found = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "add_url_rule":
            continue
        methods = _methods_from_call(call)
        if not methods:
            continue
        view_func_name = None
        for kw in call.keywords:
            if kw.arg == "view_func" and isinstance(kw.value, ast.Name):
                view_func_name = kw.value.id
        if view_func_name is None and len(call.args) >= 3 and isinstance(call.args[2], ast.Name):
            view_func_name = call.args[2].id
        if view_func_name:
            found.append((view_func_name, methods))
    return found


def _rel(path: Path, base: Path = REPO_ROOT) -> str:
    """`path` relativo a `base` quando possível; senão o path absoluto (ex.:
    testes de mutação usam um `root` em tmp_path, fora do repo real — a
    chave de ALLOWLIST não precisa bater ali, só não pode quebrar)."""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def scan_write_routes(root: Path = API_ROOT) -> list[Violation]:
    violations: list[Violation] = []

    for file in sorted(root.rglob("*.py")):
        if "__pycache__" in file.parts:
            continue
        info = _get_module_info(file)
        if info is None:
            continue
        rel = _rel(file)

        registrations: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, Path, set[str]]] = []

        for node, methods in _find_route_decorator_registrations(info.tree):
            registrations.append((node.name, node, file, methods))

        for view_func_name, methods in _find_add_url_rule_registrations(info.tree):
            resolved = _resolve_callable(view_func_name, info)
            if resolved is None:
                # Fail-closed: não conseguimos localizar o handler estaticamente
                # (import dinâmico, alias exótico) — trata como violação até
                # alguém confirmar manualmente e allowlistar com motivo.
                violations.append(Violation(
                    file=file, handler=view_func_name, handler_file=file,
                    method="/".join(sorted(methods & WRITE_METHODS)) or "?",
                    reason="handler não resolvido estaticamente (import dinâmico?) — revisar manualmente",
                ))
                continue
            handler_file, handler_node = resolved
            registrations.append((view_func_name, handler_node, handler_file, methods))

        for handler_name, node, handler_file, methods in registrations:
            for method in sorted(methods & WRITE_METHODS):
                route_id = f"{rel}::{handler_name}::{method}"
                if route_id in ALLOWLIST:
                    continue
                if not _is_route_gated(node, handler_file):
                    violations.append(Violation(
                        file=file, handler=handler_name, handler_file=handler_file,
                        method=method,
                        reason=(
                            f"sem decorator em {GATE_DECORATORS} nem chamada "
                            f"has_permission(...) alcançável a partir do handler"
                        ),
                    ))

    return violations


# ============================================================
# Catraca (ratchet) — decisão do Vitor: 77(ish) rotas pré-existentes sem gate
# não travam o CI hoje, mas o número/lista JAMAIS pode crescer. O débito fica
# registrado (e visível) em BASELINE_FILE; corrigir uma rota exige apertar a
# catraca (remover a linha dela do baseline) na mesma PR — senão o arquivo
# vira um teto confortável em vez de um registro fiel do débito real.
# ============================================================

BASELINE_FILE = REPO_ROOT / "scripts" / "write_route_gate_baseline.txt"


def _violation_key(v: Violation) -> str:
    return f"{_rel(v.file)}::{v.handler}::{v.method}"


def load_baseline(path: Path = BASELINE_FILE) -> set[str]:
    """Lê o baseline versionado. Ausente = baseline vazio (catraca no zero)."""
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keys.add(line)
    return keys


@dataclass
class RatchetResult:
    current: set[str]
    # Violação de hoje que NÃO está no baseline: rota nova sem gate. Falha.
    new_violations: set[str]
    # Entrada do baseline que NÃO é mais violação: rota já corrigida no
    # código, mas ninguém apertou a catraca removendo a linha. Falha.
    stale_baseline_entries: set[str]


def check_ratchet(violations: list[Violation], baseline: set[str]) -> RatchetResult:
    current = {_violation_key(v) for v in violations}
    return RatchetResult(
        current=current,
        new_violations=current - baseline,
        stale_baseline_entries=baseline - current,
    )


def main() -> int:
    report_only = "--report-only" in sys.argv
    violations = scan_write_routes()
    result = check_ratchet(violations, load_baseline())
    ok = not result.new_violations and not result.stale_baseline_entries

    if not ok:
        print("WRITE ROUTE PERMISSION GATE FAILED (catraca)")
        if result.new_violations:
            print()
            print(f"{len(result.new_violations)} rota(s) NOVA(s) de escrita sem gate "
                  "(fora do baseline congelado):")
            for key in sorted(result.new_violations):
                print(f"  [NOVA]   {key}")
            print()
            print("Ação: adicionar um decorator de GATE_DECORATORS (require_permission/require_admin/"
                  "require_superadmin/require_superadmin_or_404/require_training_role/"
                  "require_device_scope), ou uma chamada has_permission(\"chave:do:registry\") no "
                  "handler. Se a rota é legitimamente pública ou autentica por outro mecanismo "
                  "(device/HMAC/token one-time), adicione a ALLOWLIST com o motivo por escrito — "
                  f"NÃO adicione a {BASELINE_FILE.name}, que é só para o débito antigo.")
        if result.stale_baseline_entries:
            print()
            print(f"{len(result.stale_baseline_entries)} rota(s) do baseline já têm gate no código "
                  "mas ainda constam no arquivo congelado — a catraca tem de apertar:")
            for key in sorted(result.stale_baseline_entries):
                print(f"  [CORRIGIDA, FALTA APERTAR]  {key}")
            print()
            print(f"Ação: remova essa(s) linha(s) de {_rel(BASELINE_FILE)} nesta mesma PR — "
                  "senão o baseline vira um teto confortável em vez do débito real.")
        return 0 if report_only else 1

    print("Write route permission gate PASSED (catraca) — nenhuma rota nova sem gate, "
          "baseline em dia.")
    print(f"  ({len(ALLOWLIST)} exceção(ões) na allowlist; "
          f"{len(result.current)} rota(s) de débito pré-existente no baseline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
