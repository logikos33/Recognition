"""
CORE permissions.py — Registry canônico de permissões (WS7).

Fonte única de verdade sobre o vocabulário de permissões da plataforma.

Vocabulário canônico: 'dominio:acao' — o MESMO formato já persistido em
custom_roles.permissions (migration 052) e usado pelo frontend (types/admin.ts).
As 18 chaves snake_case legadas de ROLE_PERMISSIONS viram aliases
(LEGACY_ALIASES) e a matriz legada é DERIVADA deste registry — shape idêntica.

Cada entrada tem:
  label        — nome curto pt-BR (exibido na UI no lugar da chave técnica)
  description  — pt-BR, explica o que a permissão LIBERA (pedido explícito WS7)
  group        — agrupamento funcional para a UI
  module       — módulo de produto ('core' = plataforma toda)
  default_roles — roles que possuem a permissão POR PADRÃO. Para gates
                  convertidos (enforced=True) este role-set é EXATAMENTE o
                  role-set do check inline original — paridade garantida por
                  teste (tests/security/test_permission_gate_parity.py).
  enforced     — True quando existe gate real usando require_permission/
                 has_permission com esta chave. False = documentacional
                 (endpoint protegido por decorator de role ou sem gate).

Precedência de resolução (PermissionService):
  deny override > allow override > custom_role > default_roles(role)
  Superadmin: SEMPRE tudo — imune a deny (anti-lockout).

Related: app/core/tenant.py (has_permission/require_permission),
         app/domain/services/permission_service.py, app/constants.py
"""
from typing import Any

# Ordem canônica de roles — usada para manter listas determinísticas
ROLE_ORDER: tuple[str, ...] = (
    "superadmin", "admin", "operator", "analyst", "trainer", "viewer",
)

_ALL_ROLES = list(ROLE_ORDER)


def _entry(
    label: str,
    description: str,
    group: str,
    default_roles: list[str],
    module: str = "core",
    enforced: bool = False,
) -> dict[str, Any]:
    return {
        "label": label,
        "description": description,
        "group": group,
        "module": module,
        "default_roles": default_roles,
        "enforced": enforced,
    }


PERMISSION_REGISTRY: dict[str, dict[str, Any]] = {
    # ── Câmeras ───────────────────────────────────────────────────────────────
    "cameras:read": _entry(
        "Ver câmeras",
        "Permite visualizar a lista de câmeras e assistir ao vídeo ao vivo.",
        "Câmeras", _ALL_ROLES,
    ),
    "cameras:control": _entry(
        "Controlar câmeras",
        "Permite iniciar e parar o monitoramento de uma câmera.",
        "Câmeras", ["superadmin", "admin", "operator"],
    ),
    "cameras:configure": _entry(
        "Configurar câmeras",
        "Permite alterar configurações técnicas da câmera (FPS, modelo, conexão).",
        "Câmeras", ["superadmin", "admin"],
    ),
    "cameras:write": _entry(
        "Cadastrar/editar câmeras",
        "Permite cadastrar novas câmeras e editar nome, local e credenciais.",
        "Câmeras", ["superadmin", "admin"],
    ),
    "cameras:delete": _entry(
        "Remover câmeras",
        "Permite excluir câmeras do sistema. Ação irreversível.",
        "Câmeras", ["superadmin", "admin"],
    ),
    "cameras:test": _entry(
        "Testar conexão de câmera",
        "Permite testar a conectividade de uma câmera (probe RTSP) antes de salvar.",
        "Câmeras", ["superadmin", "admin", "operator"], enforced=True,
    ),
    # ── Alertas ───────────────────────────────────────────────────────────────
    "alerts:read": _entry(
        "Ver alertas",
        "Permite visualizar o histórico de alertas e detecções.",
        "Alertas", ["superadmin", "admin", "operator", "analyst", "viewer"],
    ),
    "alerts:feedback": _entry(
        "Dar feedback em alertas",
        "Permite marcar alertas como corretos ou falsos positivos (melhora o modelo).",
        "Alertas", ["superadmin", "admin", "operator", "analyst"],
    ),
    "alerts:export": _entry(
        "Exportar alertas",
        "Permite exportar o histórico de alertas em CSV/Excel.",
        "Alertas", ["superadmin", "admin", "operator", "analyst"],
    ),
    # ── Treinamento ───────────────────────────────────────────────────────────
    "frames:annotate": _entry(
        "Anotar frames",
        "Permite desenhar e validar anotações (bounding boxes) em frames de treinamento.",
        "Treinamento", ["superadmin", "admin", "operator", "trainer"],
    ),
    "training:read": _entry(
        "Ver treinamentos",
        "Permite acompanhar jobs de treinamento, datasets e modelos do tenant.",
        "Treinamento", ["superadmin", "admin", "trainer"],
    ),
    "training:write": _entry(
        "Criar treinamentos",
        "Permite criar e disparar novos jobs de treinamento de modelo.",
        "Treinamento", ["superadmin", "admin", "trainer"],
    ),
    "training:approve": _entry(
        "Aprovar treinamentos",
        "Permite aprovar ou rejeitar treinamentos pendentes de revisão da plataforma.",
        "Treinamento", ["superadmin"],
    ),
    "models:approve": _entry(
        "Aprovar modelos",
        "Permite aprovar a publicação de um modelo treinado para uso em produção.",
        "Treinamento", ["superadmin", "admin"],
    ),
    # ── Relatórios ────────────────────────────────────────────────────────────
    "reports:read": _entry(
        "Ver relatórios",
        "Permite visualizar dashboards e relatórios de indicadores.",
        "Relatórios", ["superadmin", "admin", "operator", "analyst", "viewer"],
    ),
    "reports:export": _entry(
        "Exportar relatórios",
        "Permite exportar relatórios e dashboards em Excel/PDF.",
        "Relatórios", ["superadmin", "admin", "operator", "analyst", "viewer"],
    ),
    # ── Retenção & Armazenamento ─────────────────────────────────────────────
    "retention:write": _entry(
        "Alterar retenção de vídeos",
        "Permite definir por quantos dias os vídeos e evidências ficam armazenados.",
        "Retenção", ["superadmin", "admin"], enforced=True,
    ),
    # ── Notificações ──────────────────────────────────────────────────────────
    "notifications:manage": _entry(
        "Gerenciar notificações",
        "Permite criar, editar e remover canais de notificação (WhatsApp, e-mail, webhook).",
        "Notificações", ["superadmin", "admin"], enforced=True,
    ),
    # ── Dispositivos & Edge ───────────────────────────────────────────────────
    "devices:manage": _entry(
        "Gerenciar dispositivos",
        "Permite gerar códigos de pareamento para conectar novos dispositivos edge.",
        "Dispositivos & Edge", ["superadmin", "admin"], enforced=True,
    ),
    "edge:manage": _entry(
        "Gerenciar sites edge",
        "Permite criar e administrar sites edge, tokens de enrollment e devices locais.",
        "Dispositivos & Edge", ["superadmin", "admin"], enforced=True,
    ),
    "gateways:manage": _entry(
        "Gerenciar gateways",
        "Permite configurar o gateway de rede (MikroTik/WireGuard) de um site.",
        "Dispositivos & Edge", ["superadmin", "admin"], enforced=True,
    ),
    # ── Aparência ────────────────────────────────────────────────────────────
    "branding:write": _entry(
        "Personalizar aparência",
        "Permite alterar logo, cores e nome do produto exibidos para o tenant.",
        "Aparência", ["superadmin", "admin"],
    ),
    # ── Administração ────────────────────────────────────────────────────────
    "admin:users": _entry(
        "Gerenciar usuários",
        "Permite criar, editar, ativar e desativar usuários do tenant.",
        "Administração", ["superadmin", "admin"],
    ),
    "admin:roles": _entry(
        "Gerenciar roles",
        "Permite criar e editar roles customizadas com permissões granulares.",
        "Administração", ["superadmin", "admin"],
    ),
    "admin:settings": _entry(
        "Configurar tenant",
        "Permite alterar configurações gerais do tenant (planos, módulos, políticas).",
        "Administração", ["superadmin"],
    ),
    "admin:panel": _entry(
        "Acessar painel admin",
        "Permite acessar o painel administrativo da plataforma (superadmin).",
        "Administração", ["superadmin"],
    ),
    "workers:manage": _entry(
        "Gerenciar workers",
        "Permite monitorar e reiniciar os workers de inferência da plataforma.",
        "Administração", ["superadmin"],
    ),
    "plans:manage": _entry(
        "Gerenciar planos",
        "Permite criar e editar planos comerciais e limites por plano.",
        "Administração", ["superadmin"],
    ),
    "announcements:manage": _entry(
        "Gerenciar comunicados",
        "Permite publicar e editar comunicados exibidos aos tenants.",
        "Administração", ["superadmin"],
    ),
    "audit:read": _entry(
        "Ver log de auditoria",
        "Permite consultar o registro de ações administrativas (audit log).",
        "Administração", ["superadmin"],
    ),
    "tickets:manage": _entry(
        "Gerenciar tickets",
        "Permite abrir, responder e encerrar tickets de suporte.",
        "Administração", ["superadmin", "admin"],
    ),
    # ── Contagem ──────────────────────────────────────────────────────────────
    "counting:read": _entry(
        "Ver contagens",
        "Permite visualizar sessões e resultados de contagem de objetos.",
        "Contagem", ["superadmin", "admin", "operator", "analyst", "viewer"],
        module="counting",
    ),
    "counting:write": _entry(
        "Operar contagens",
        "Permite iniciar, pausar e encerrar sessões de contagem.",
        "Contagem", ["superadmin", "admin", "operator"], module="counting",
    ),
    # ── Verificação ───────────────────────────────────────────────────────────
    "verification:read": _entry(
        "Ver fila de verificação",
        "Permite visualizar a fila de detecções pendentes de verificação humana.",
        "Verificação", ["superadmin", "admin", "operator", "analyst"],
    ),
    "verification:write": _entry(
        "Verificar detecções",
        "Permite aprovar, rejeitar ou corrigir detecções na fila de verificação.",
        "Verificação", ["superadmin", "admin", "operator"],
    ),
}

# Chaves snake_case legadas (ROLE_PERMISSIONS pré-WS7) → chave canônica.
# A matriz legada (GET /api/v1/admin/permissions/matrix) é derivada via
# legacy_role_permissions() — shape byte-compatível (contract test).
LEGACY_ALIASES: dict[str, str] = {
    "view_cameras": "cameras:read",
    "control_cameras": "cameras:control",
    "view_alerts": "alerts:read",
    "feedback_alerts": "alerts:feedback",
    "annotate_frames": "frames:annotate",
    "create_training_job": "training:write",
    "approve_model": "models:approve",
    "view_reports": "reports:read",
    "manage_users": "admin:users",
    "configure_cameras": "cameras:configure",
    "manage_tenant": "admin:settings",
    "view_admin_panel": "admin:panel",
    "approve_training": "training:approve",
    "manage_workers": "workers:manage",
    "manage_plans": "plans:manage",
    "manage_announcements": "announcements:manage",
    "view_audit_log": "audit:read",
    "manage_tickets": "tickets:manage",
}


def normalize_key(key: str) -> str | None:
    """Resolve chave (canônica ou alias legado) para a canônica.

    Retorna None se a chave não existe no registry — chamadores devem
    rejeitar/ignorar chaves desconhecidas (validação de input).
    """
    if key in PERMISSION_REGISTRY:
        return key
    return LEGACY_ALIASES.get(key)


def default_roles_for(key: str) -> tuple[str, ...]:
    """Roles-padrão de uma permissão (resolve alias). Vazio se desconhecida."""
    canonical = normalize_key(key)
    if canonical is None:
        return ()
    return tuple(PERMISSION_REGISTRY[canonical]["default_roles"])


def permissions_for_role(role: str) -> list[str]:
    """Permissões canônicas que a role possui por padrão (ordenadas)."""
    return sorted(
        key for key, meta in PERMISSION_REGISTRY.items()
        if role in meta["default_roles"]
    )


def all_permission_keys() -> list[str]:
    """Todas as chaves canônicas do registry (ordenadas)."""
    return sorted(PERMISSION_REGISTRY.keys())


def legacy_role_permissions() -> dict[str, list[str]]:
    """Deriva a matriz legada ROLE_PERMISSIONS a partir do registry.

    Shape idêntica à constante literal pré-WS7: {chave_snake: [roles]},
    com roles na ordem canônica ROLE_ORDER.
    """
    matrix: dict[str, list[str]] = {}
    for legacy_key, canonical in LEGACY_ALIASES.items():
        roles = PERMISSION_REGISTRY[canonical]["default_roles"]
        matrix[legacy_key] = [r for r in ROLE_ORDER if r in roles]
    return matrix


def registry_as_list() -> list[dict[str, Any]]:
    """Registry serializado para a API (GET /permissions/registry)."""
    return [
        {
            "key": key,
            "label": meta["label"],
            "description": meta["description"],
            "group": meta["group"],
            "module": meta["module"],
            "default_roles": list(meta["default_roles"]),
            "enforced": meta["enforced"],
        }
        for key, meta in sorted(PERMISSION_REGISTRY.items())
    ]
