"""
Recognition — Tenant Class Service (WS-A1).

Classes de anotação escopadas por tenant_id + module_code (migration 093),
com fallback user_id para linhas legadas (tenant_id NULL, anteriores ao
backfill). Contrato do AnnotationInterface.jsx preservado: id, name, color.

Regras:
  - Toda query passa por AnnotationRepository (zero SQL aqui).
  - DELETE recusa classe referenciada por frame_annotations (409) — o schema
    tem ON DELETE CASCADE e apagaria anotações silenciosamente sem o gate.
  - color VARCHAR(7) no schema → apenas #RRGGBB.

PENDÊNCIA CONHECIDA (achado da revisão adversarial, NÃO corrigida aqui):
  A constraint real no banco é UNIQUE(user_id, name) — migration 003, nunca
  estendida para incluir module_code quando a 093 adicionou o escopo por
  módulo. Resultado: o MESMO usuário não pode ter duas classes com o MESMO
  nome em módulos DIFERENTES (ex.: "helmet" em epi E em quality) — o create
  do segundo módulo recebe 409 mesmo sendo um par (user, module, name)
  distinto. Corrigir exigiria uma migration com DROP CONSTRAINT + novo
  UNIQUE(user_id, module_code, name) — a política deste projeto proíbe
  DROP em migrations (CLAUDE.md: "NUNCA em Migrations: DROP"), então esta
  correção requer decisão humana explícita (exceção à política) antes de
  qualquer migration; não implementada nesta branch. Ver ADR-0037.

  ADENDO (achado no PR do fix do anotador "classe some" — mesma constraint,
  ângulo cross-tenant): UNIQUE(user_id, name) também barra o MESMO nome de
  classe em TENANTS diferentes quando o user_id é compartilhado — ex.: um
  superadmin operando sob contexto assumido (POST /tenants/<id>/assume, ADR-
  0019/#302) cria "Capacete" pro tenant A e depois tenta criar "Capacete"
  pro tenant B: 409 falso-positivo, porque a constraint enxerga (user_id=
  superadmin, name="Capacete") duas vezes, ignorando que tenant_id difere.
  Mesma causa raiz do pendência acima (a constraint nunca foi migrada pra
  acompanhar o escopo real, que é tenant_id [+ module_code]); mesma solução
  bloqueada pela mesma política de migration (precisaria DROP CONSTRAINT).
  Registrado aqui em vez de forçado — decisão de criar a migration com
  exceção explícita fica para o humano.
"""
import logging
import re
from typing import Any
from uuid import UUID

import psycopg2.errors

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.services.class_namespace import namespace_tenant_class_id
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)

logger = logging.getLogger(__name__)

DEFAULT_COLOR = "#3b82f6"
DEFAULT_MODULE = "epi"
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_MODULE_CODE_RE = re.compile(r"^[a-z0-9_]{1,50}$")
_NAME_MAX_LEN = 100  # yolo_classes.name VARCHAR(100)


class TenantClassService:
    """Use cases de classes do tenant (CRUD + contagem de amostras)."""

    def __init__(self, annotation_repo: AnnotationRepository) -> None:
        self._repo = annotation_repo

    def list_classes(
        self,
        tenant_id: str,
        user_id: "UUID | None" = None,
        module_code: str = DEFAULT_MODULE,
        include_counts: bool = False,
    ) -> list[dict[str, Any]]:
        """Lista classes do tenant+módulo (fallback user_id p/ legado).

        include_counts=True adiciona annotation_count (amostras por classe
        via JOIN frame_annotations).
        """
        module = self._normalize_module(module_code)
        if include_counts:
            return self._repo.get_classes_with_counts(
                str(tenant_id), user_id=user_id, module_code=module
            )
        return self._repo.get_classes_for_tenant(
            str(tenant_id), user_id=user_id, module_code=module
        )

    def create_class(
        self,
        user_id: UUID,
        tenant_id: str,
        name: str,
        color: str = DEFAULT_COLOR,
        module_code: str = DEFAULT_MODULE,
        is_violation: "bool | None" = None,
    ) -> dict[str, Any]:
        """Cria classe tenant-scoped. 409 se nome duplicado (UNIQUE user+name).

        `is_violation` é OBRIGATÓRIO (achado da revisão adversarial, contrato
        A1): o INSERT nunca gravava a coluna, então TODA classe criada pelo
        Estúdio nascia com `is_violation IS NULL` — 'observação' não era caso
        de borda, era o estado de nascimento de 100% das classes do tenant.
        Migration 127 já documentava o dia em que uma rota passaria a gravar
        isto; este é esse dia — exigir aqui, na única porta de entrada viva,
        fecha a lacuna sem tocar a coluna nullable (uma classe do catálogo
        global legado ou uma linha antiga sem decisão continuam existindo,
        só não é mais possível CRIAR uma nova indecidida)."""
        clean_name = self._validate_name(name)
        clean_color = self._validate_color(color)
        module = self._normalize_module(module_code)
        if is_violation is None:
            raise ValidationError(
                "Informe is_violation (true = violação, false = conformidade) "
                "— toda classe precisa nascer com a polaridade decidida"
            )
        self._reject_if_in_global_catalog(module, clean_name)
        try:
            return self._repo.create_class(
                user_id,
                clean_name,
                clean_color,
                tenant_id=tenant_id,
                module_code=module,
                is_violation=bool(is_violation),
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise ConflictError(f"Classe '{clean_name}' já existe") from exc

    def update_class(
        self,
        class_id: int,
        tenant_id: str,
        user_id: "UUID | None" = None,
        name: "str | None" = None,
        color: "str | None" = None,
    ) -> dict[str, Any]:
        """Renomeia e/ou recolore classe. 404 se de outro tenant."""
        if name is None and color is None:
            raise ValidationError("Informe name e/ou color para atualizar")
        clean_name = self._validate_name(name) if name is not None else None
        clean_color = self._validate_color(color) if color is not None else None
        if clean_name is not None:
            # Mesmo guard de create/patch (ADR-0071): este é o PUT legado —
            # sem isto, renomear por AQUI para um nome do catálogo global
            # abria a mesma duplicata que já foi fechada nas outras duas
            # portas de entrada (achado do veredito: só POST e PATCH tinham
            # o guard, PUT continuava passando).
            existing = self._repo.get_class_for_tenant(
                int(class_id), str(tenant_id), user_id=user_id
            )
            if not existing:
                raise NotFoundError("Classe", str(class_id))
            self._reject_if_in_global_catalog(
                existing.get("module_code", DEFAULT_MODULE), clean_name
            )
        try:
            updated = self._repo.update_class(
                int(class_id),
                str(tenant_id),
                name=clean_name,
                color=clean_color,
                user_id=user_id,
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise ConflictError(f"Classe '{clean_name}' já existe") from exc
        if not updated:
            raise NotFoundError("Classe", str(class_id))
        return updated

    def patch_class(
        self,
        class_id: int,
        tenant_id: str,
        name: "str | None" = None,
        color: "str | None" = None,
        display_order: "int | None" = None,
        archived: "bool | None" = None,
        is_violation: "bool | None" = None,
    ) -> dict[str, Any]:
        """Atualiza campos parciais de uma classe do tenant (PATCH /classes/<id>,
        migration 110). Todos os campos são opcionais; None = não veio no
        payload (mantém valor atual — mesma semântica de update_class).

        404 se a classe é do catálogo global (module_classes não tem
        contraparte em yolo_classes) ou de outro tenant — get_class_for_tenant
        já escopa por tenant_id, então um id que só existe no catálogo ou em
        outro tenant simplesmente não é encontrado.
        """
        if (
            name is None
            and color is None
            and display_order is None
            and archived is None
            and is_violation is None
        ):
            raise ValidationError(
                "Informe ao menos um campo (name, color, display_order, "
                "archived, is_violation)"
            )

        existing = self._repo.get_class_for_tenant(int(class_id), str(tenant_id))
        if not existing:
            raise NotFoundError("Classe", str(class_id))

        fields: dict[str, Any] = {}
        if name is not None:
            fields["name"] = self._validate_name(name)
            # Mesma regra da criação (ADR-0071): renomear PARA um nome que já
            # existe no catálogo global duplicaria a classe do mesmo jeito.
            self._reject_if_in_global_catalog(
                existing.get("module_code", DEFAULT_MODULE), fields["name"]
            )
        if color is not None:
            fields["color"] = self._validate_color(color)
        if display_order is not None:
            fields["display_order"] = int(display_order)
        if archived is not None:
            fields["archived"] = bool(archived)
        if is_violation is not None:
            # Polaridade da classe (ADR-0065): ausência é violação, presença é
            # conformidade. Fonte de verdade de quem decide alerta — antes só
            # existia por SQL manual, e cadastro de cliente não pode depender
            # de sessão de engenharia.
            fields["is_violation"] = bool(is_violation)

        try:
            updated = self._repo.patch_class(int(class_id), str(tenant_id), fields)
        except psycopg2.errors.UniqueViolation as exc:
            raise ConflictError(f"Classe '{fields.get('name')}' já existe") from exc
        if not updated:
            raise NotFoundError("Classe", str(class_id))
        return updated

    def delete_class(
        self,
        class_id: int,
        tenant_id: str,
        user_id: "UUID | None" = None,
    ) -> dict[str, Any]:
        """Deleta classe sem anotações vinculadas.

        404 se de outro tenant; 409 se frame_annotations referenciam
        (contagem ANTES do delete + guarda NOT EXISTS no SQL contra corrida).

        A contagem/guarda usa o id NAMESPACED (class_namespace.
        namespace_tenant_class_id) — é esse o valor efetivamente gravado em
        frame_annotations.class_id para uma classe do tenant (achado:
        contar/checar pelo id cru de yolo_classes sempre dava zero, porque
        migration 103 tirou a FK e frame_annotations nunca usou o id cru;
        o guard NOT EXISTS "passava" mesmo com anotações reais vinculadas).
        """
        existing = self._repo.get_class_for_tenant(
            int(class_id), str(tenant_id), user_id=user_id
        )
        if not existing:
            raise NotFoundError("Classe", str(class_id))

        namespaced_id = namespace_tenant_class_id(int(class_id))
        refs = self._repo.count_annotations_for_class(namespaced_id)
        if refs > 0:
            raise ConflictError(
                f"Classe possui {refs} anotações vinculadas — arquive a "
                "classe (PATCH /api/classes/<id> com {\"archived\": true}) "
                "em vez de excluir; excluir apagaria a referência das "
                "caixas já anotadas"
            )

        deleted = self._repo.delete_class(
            int(class_id), str(tenant_id), user_id=user_id,
            referenced_class_id=namespaced_id,
        )
        if deleted == 0:
            # Corrida: anotação criada entre o count e o delete (guarda SQL)
            raise ConflictError(
                "Classe possui anotações vinculadas — deleção abortada"
            )
        logger.info(
            "class_deleted: id=%s tenant=%s name=%s",
            class_id,
            tenant_id,
            existing.get("name"),
        )
        return existing

    # --- Validação -------------------------------------------------------

    _ROTULO_POLARIDADE = {True: "violação", False: "conformidade", None: "indefinida"}

    def _reject_if_in_global_catalog(self, module_code: str, name: str) -> None:
        """ADR-0071 — a polaridade servida é a UNIÃO global ∪ tenant
        (AlertRepository._nomes_por_polaridade), casando pelos DOIS nomes do
        catálogo global. Criar (ou renomear para) um nome que já existe lá
        NÃO substitui a linha global — a união nunca subtrai — só duplica a
        classe na tela sem separar o uso: achado de 01/09, 'Sem Óculos' e
        mais duas nasceram homônimas do global e ficaram com usage_count=0
        para sempre, porque as anotações antigas continuam presas ao
        class_id global. Mesma regra que
        scripts/ops/aplicar_calibracao_rvb.py passou a aplicar depois do
        incidente."""
        global_row = self._repo.find_in_global_catalog(module_code, name)
        if not global_row:
            return
        polaridade = self._ROTULO_POLARIDADE[global_row["is_violation"]]
        raise ConflictError(
            f"'{name}' já existe no catálogo padrão do sistema, com "
            f"polaridade {polaridade}. Criar (ou renomear para) o mesmo "
            "nome aqui não substitui o padrão — as duas passam a contar "
            "juntas, e a tela mostra o nome duplicado. Escolha outro nome."
        )

    @staticmethod
    def _validate_name(name: str) -> str:
        clean = (name or "").strip()
        if not clean:
            raise ValidationError("Nome da classe é obrigatório")
        if len(clean) > _NAME_MAX_LEN:
            raise ValidationError(
                f"Nome da classe deve ter no máximo {_NAME_MAX_LEN} caracteres"
            )
        return clean

    @staticmethod
    def _validate_color(color: str) -> str:
        clean = (color or "").strip()
        if not _HEX_COLOR_RE.match(clean):
            raise ValidationError("Cor inválida — use formato #RRGGBB")
        return clean

    @staticmethod
    def _normalize_module(module_code: str) -> str:
        clean = (module_code or "").strip().lower() or DEFAULT_MODULE
        if not _MODULE_CODE_RE.match(clean):
            raise ValidationError("module inválido — use [a-z0-9_], máx 50")
        return clean
