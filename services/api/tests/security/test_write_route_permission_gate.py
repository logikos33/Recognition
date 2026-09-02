"""
Tests: scripts/check_write_route_permission_gate.py — regra permanente:
nenhuma rota de ESCRITA (POST/PUT/PATCH/DELETE) sob services/api/app/api/
pode ficar sem gate de permissão explícito (decorator, `has_permission(...)`
inline, ou o padrão legado `get_role()` comparado a um role — ver docstring
do script para os três mecanismos).

Motivação (P0 real, achado nesta rodada de mutirão): POST /api/training/jobs
tinha `@limiter.limit(...)` + `@jwt_required()` e ZERO gate de permissão —
qualquer usuário autenticado, de qualquer papel, disparava treino real (GPU
paga). `@jwt_required()` só prova QUEM é o usuário — nunca O QUE ele pode
fazer. Esse buraco só foi achado varrendo manualmente o código; este teste
transforma a varredura numa regra que roda em todo PR.

Igual ao padrão de tests/unit/test_license_gate_import_scan.py: o script
mora fora de services/api/ (scripts/ na raiz do repo) e é importado aqui via
importlib a partir do caminho do arquivo.

Corrigir as ~70 rotas sem gate hoje NÃO é escopo desta task — decisão do
Vitor: CATRACA. A régua congela essa lista em
scripts/write_route_gate_baseline.txt e só fica vermelha quando ela CRESCE
(rota nova sem gate) ou fica desatualizada para menos (rota corrigida cuja
linha ninguém removeu do baseline — ver TestCatracaNaoRegride abaixo).
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[4] / "scripts" / "check_write_route_permission_gate.py"
)


def _load_gate_module():
    spec = importlib.util.spec_from_file_location(
        "check_write_route_permission_gate", _MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_write_route_permission_gate"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


gate = _load_gate_module()


# --------------------------------------------------------------------------
# Unidade: helpers de AST — a robustez que regex não dá (decorator em
# qualquer ordem, com ou sem argumento; atalho @bp.post(...) vs @bp.route(...)
# com methods=; get_role() usado só pra log não deve contar como gate).
# --------------------------------------------------------------------------


class TestDecoratorDetection:
    def test_decorator_with_call_and_args(self) -> None:
        dec = ast.parse("@require_permission('x')\ndef f(): pass").body[0].decorator_list[0]
        assert gate._decorator_root_name(dec) == "require_permission"

    def test_decorator_bare_name_no_call(self) -> None:
        dec = ast.parse("@require_admin\ndef f(): pass").body[0].decorator_list[0]
        assert gate._decorator_root_name(dec) == "require_admin"

    def test_decorator_order_does_not_matter(self) -> None:
        names_a = {
            gate._decorator_root_name(d)
            for d in ast.parse("@jwt_required()\n@require_superadmin\ndef f(): pass").body[0].decorator_list
        }
        names_b = {
            gate._decorator_root_name(d)
            for d in ast.parse("@require_superadmin\n@jwt_required()\ndef f(): pass").body[0].decorator_list
        }
        assert names_a == names_b == {"jwt_required", "require_superadmin"}


class TestRouteRegistrationStyles:
    def test_route_with_methods_kwarg(self) -> None:
        tree = ast.parse("@bp.route('/x', methods=['POST', 'GET'])\ndef f(): pass")
        regs = gate._find_route_decorator_registrations(tree)
        assert regs[0][1] == {"POST", "GET"}

    def test_shorthand_post_infers_method_without_methods_kwarg(self) -> None:
        """admin/integration_routes.py e admin/test_console_routes.py usam só
        o atalho `@bp.post(...)` — sem isso, essas rotas ficam invisíveis ao
        scan (pior que falso positivo: um "tudo limpo" que nem viu a rota)."""
        tree = ast.parse("@bp.post('/x')\ndef f(): pass")
        regs = gate._find_route_decorator_registrations(tree)
        assert regs[0][1] == {"POST"}

    def test_get_only_route_is_ignored(self) -> None:
        tree = ast.parse("@bp.route('/x')\ndef f(): pass")
        assert gate._find_route_decorator_registrations(tree) == []

    def test_add_url_rule_extracts_view_func_and_methods(self) -> None:
        """cameras/routes.py, models/routes.py e counting/routes.py registram
        assim (não com @bp.route direto) — o handler mora noutro arquivo."""
        tree = ast.parse("bp.add_url_rule('/x', view_func=create_x, methods=['POST'])")
        assert gate._find_add_url_rule_registrations(tree) == [("create_x", {"POST"})]


class TestInlineGateDetection:
    def test_role_compare_via_assigned_variable(self) -> None:
        node = ast.parse(
            "def f():\n"
            "    role = get_role()\n"
            "    if role not in ('admin', 'superadmin'):\n"
            "        return error('no', 403)\n"
        ).body[0]
        assert gate._has_inline_role_check(node) is True

    def test_role_compare_direct_call(self) -> None:
        node = ast.parse(
            "def f():\n"
            "    if get_role() not in _ADMIN_ROLES:\n"
            "        return error('no', 403)\n"
        ).body[0]
        assert gate._has_inline_role_check(node) is True

    def test_get_role_used_only_for_logging_is_not_a_gate(self) -> None:
        """`actor_role=get_role()` passado pra auditoria, sem NENHUMA
        comparação, não restringe ninguém — não deve contar como gate
        (senão o scanner ficaria cego pra rotas de verdade sem check)."""
        node = ast.parse(
            "def f():\n"
            "    log_audit(actor_role=get_role())\n"
            "    return success({})\n"
        ).body[0]
        assert gate._has_inline_role_check(node) is False


# --------------------------------------------------------------------------
# Mutação controlada (tmp_path, isolado — não toca em nenhum arquivo real):
# decorator presente → passa; removido → a regra fica vermelha.
# --------------------------------------------------------------------------


class TestMutacaoControlada:
    def _write_widget_route(self, tmp_path: Path, *, gated: bool) -> Path:
        api_root = tmp_path / "services" / "api" / "app" / "api"
        pkg = api_root / "v1" / "widgets"
        pkg.mkdir(parents=True)
        gate_line = '@require_permission("widgets:write")\n' if gated else ""
        (pkg / "routes.py").write_text(
            "from flask import Blueprint\n"
            "from flask_jwt_extended import jwt_required\n\n"
            "widgets_bp = Blueprint('widgets', __name__)\n\n"
            '@widgets_bp.route("/widgets", methods=["POST"])\n'
            "@jwt_required()\n"
            f"{gate_line}"
            "def create_widget():\n"
            "    return {}\n"
        )
        return api_root

    def test_gated_route_passes(self, tmp_path: Path) -> None:
        root = self._write_widget_route(tmp_path, gated=True)
        assert gate.scan_write_routes(root) == []

    def test_removing_decorator_turns_the_rule_red(self, tmp_path: Path) -> None:
        """A mutação exigida pela task: tirar o decorator de uma rota
        qualquer faz a regra acusar — sem isso a régua podia estar sempre
        verde por acidente e ninguém notaria."""
        root = self._write_widget_route(tmp_path, gated=False)
        violations = gate.scan_write_routes(root)
        assert len(violations) == 1
        assert violations[0].handler == "create_widget"
        assert violations[0].method == "POST"


# --------------------------------------------------------------------------
# Estado real do repo.
# --------------------------------------------------------------------------


class TestAchadoTrainingJobsEIrmaoQuality:
    """Os dois achados P0 que motivaram esta task/rodada: POST
    /api/training/jobs (training) e POST /api/v1/quality/training/jobs
    (achado irmão, mesmo blueprint de módulo, mesma vulnerabilidade) — ambos
    JÁ corrigidos (require_training_role("approve")); provam que o próprio
    scanner reconhece o gate certo quando ele existe."""

    def test_training_create_job_is_gated_today(self) -> None:
        flagged = {(v.handler, v.method) for v in gate.scan_write_routes()}
        assert ("create_job", "POST") not in flagged, (
            "POST /api/training/jobs voltou a aparecer sem gate — regressão "
            "no require_training_role('approve') de training/routes.py."
        )

    def test_quality_create_training_job_is_gated_today(self) -> None:
        flagged = {(v.handler, v.method) for v in gate.scan_write_routes()}
        assert ("create_training_job", "POST") not in flagged, (
            "POST /api/v1/quality/training/jobs voltou a aparecer sem gate — "
            "regressão no require_training_role('approve') de quality/routes.py."
        )


class TestCatracaNaoRegride:
    """Regra permanente (decisão do Vitor): a lista de débito em
    write_route_gate_baseline.txt não pode CRESCER (rota nova sem gate) nem
    ficar DESATUALIZADA PARA MENOS (rota corrigida cuja linha ninguém tirou
    do baseline — vira teto confortável em vez de débito real registrado).

    Mutação provada nas duas direções rodando este arquivo manualmente (ver
    relatório da PR para a saída real):
      (a) remover @require_training_role("approve") de
          quality/routes.py::create_training_job (sem tocar no baseline)
          -> test_no_new_write_route_without_gate_beyond_baseline fica RED,
          apontando exatamente a rota nova.
      (b) adicionar um gate real a uma rota do baseline (ex.: @require_admin
          em admin/routes.py::mark_announcement_read) sem remover a linha
          correspondente do baseline -> test_baseline_is_not_stale fica RED,
          apontando exatamente a rota que precisa sair do arquivo.
    """

    def test_no_new_write_route_without_gate_beyond_baseline(self) -> None:
        violations = gate.scan_write_routes()
        baseline = gate.load_baseline()
        result = gate.check_ratchet(violations, baseline)
        lines = "\n".join(f"  {k}" for k in sorted(result.new_violations))
        assert result.new_violations == set(), (
            f"{len(result.new_violations)} rota(s) NOVA(s) de escrita sem gate "
            f"(fora do baseline congelado em {gate.BASELINE_FILE.name}):\n{lines}\n\n"
            "Ação: adicionar um decorator de gate.GATE_DECORATORS ou uma chamada "
            'has_permission("chave:do:registry") na rota. Se for exceção '
            "legítima (device/HMAC/token one-time), registrar em gate.ALLOWLIST "
            "com motivo — NUNCA adicionar a linha ao baseline (ele é só para o "
            "débito que já existia antes desta regra)."
        )

    def test_baseline_is_not_stale(self) -> None:
        violations = gate.scan_write_routes()
        baseline = gate.load_baseline()
        result = gate.check_ratchet(violations, baseline)
        lines = "\n".join(f"  {k}" for k in sorted(result.stale_baseline_entries))
        assert result.stale_baseline_entries == set(), (
            f"{len(result.stale_baseline_entries)} rota(s) do baseline já têm gate "
            f"no código, mas a linha continua em {gate.BASELINE_FILE.name}:\n{lines}\n\n"
            "Ação: remova essa(s) linha(s) do baseline nesta mesma PR — a catraca "
            "tem de apertar quando uma rota é corrigida, senão o arquivo vira um "
            "teto confortável em vez do débito real."
        )


class TestCheckRatchetUnitario:
    """check_ratchet() isolado — evita depender do estado real do repo pra
    provar a lógica de comparação em si (rápido, determinístico)."""

    def test_rota_nova_fora_do_baseline_e_new_violation(self) -> None:
        v = gate.Violation(
            file=Path("x.py"), handler="h", handler_file=Path("x.py"),
            method="POST", reason="sem gate",
        )
        result = gate.check_ratchet([v], baseline=set())
        assert result.new_violations == {"x.py::h::POST"}
        assert result.stale_baseline_entries == set()

    def test_baseline_sem_violacao_correspondente_e_stale(self) -> None:
        result = gate.check_ratchet([], baseline={"x.py::h::POST"})
        assert result.new_violations == set()
        assert result.stale_baseline_entries == {"x.py::h::POST"}

    def test_baseline_bate_com_violacao_atual_fica_limpo(self) -> None:
        v = gate.Violation(
            file=Path("x.py"), handler="h", handler_file=Path("x.py"),
            method="POST", reason="sem gate",
        )
        result = gate.check_ratchet([v], baseline={"x.py::h::POST"})
        assert result.new_violations == set()
        assert result.stale_baseline_entries == set()

    def test_load_baseline_ignora_comentarios_e_linhas_vazias(self, tmp_path: Path) -> None:
        f = tmp_path / "baseline.txt"
        f.write_text("# comentário\n\nx.py::h::POST\n  \n")
        assert gate.load_baseline(f) == {"x.py::h::POST"}

    def test_load_baseline_ausente_e_vazio(self, tmp_path: Path) -> None:
        assert gate.load_baseline(tmp_path / "nao-existe.txt") == set()
