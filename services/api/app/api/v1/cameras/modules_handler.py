"""
CAMERA modules_handler.py — o vínculo N:N câmera↔módulo (migration 134).

Endpoints:
  GET /api/cameras/modules  — câmeras do tenant + módulos declarados de cada
                              uma + módulos que este tenant pode declarar
  PUT /api/cameras/modules  — declara os módulos de UMA OU VÁRIAS câmeras

POR QUE UM SÓ ENDPOINT PARA UMA E PARA VÁRIAS CÂMERAS
Salvar uma câmera é `camera_ids` de tamanho 1. Uma rota por câmera obrigaria a
ação em massa a disparar N requisições em paralelo — e foi exatamente isso que
estourou o pool de conexões da API nas 28 câmeras do RVB na aba "Modelos por
câmera" (ver model_config_handlers.list_camera_model_configs). Uma requisição,
uma transação.

ISTO NÃO É `PATCH /api/cameras/<id>/module` (module_handler.py)
Aquele grava `cameras.active_module`, coluna 1:1 que o worker lê para resolver
o modelo da câmera. Continua existindo e não é tocado aqui. Esta rota grava
outra coisa: PARA QUE a câmera serve, que pode ser mais de uma coisa ao mesmo
tempo. Enquanto a coleta e o dashboard não passarem a ler camera_modules, o
que se grava aqui é declaração — e a tela diz isso com todas as letras em vez
de fingir efeito que não tem.
"""
import logging
from typing import Any
from uuid import UUID

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.core.responses import error, success
from app.core.tenant import require_permission
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_module_repository import (
    CameraModuleRepository,
)
from app.infrastructure.database.repositories.camera_repository import CameraRepository

from .module_handler import _fetch_tenant_modules, _is_module_allowed

logger = logging.getLogger(__name__)

#: Teto de câmeras por chamada. O RVB tem 29; 200 cobre um tenant grande com
#: folga e ainda impede que um payload absurdo vire uma transação sem fim.
_MAX_CAMERAS_POR_CHAMADA = 200


def _get_camera_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


def _get_link_repo() -> CameraModuleRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraModuleRepository(pool)


def _modules_do_tenant() -> list[str]:
    """Módulos que ESTE tenant pode declarar — a mesma fonte de _is_module_allowed.

    Claim 'modules' do JWT quando presente; senão tenants.modules_enabled no
    banco (token antigo). Fail-closed: erro de leitura devolve lista vazia, e
    aí a tela mostra "nenhum módulo liberado" em vez de oferecer opção que a
    escrita vai recusar.
    """
    from flask_jwt_extended import get_jwt

    modules = get_jwt().get("modules")
    if isinstance(modules, list):
        return [str(m) for m in modules]
    return _fetch_tenant_modules()


def _mapa_de_vinculos(tenant_id: str) -> dict[str, list[str]]:
    mapa: dict[str, list[str]] = {}
    for row in _get_link_repo().list_by_tenant(tenant_id):
        mapa.setdefault(str(row["camera_id"]), []).append(row["module_code"])
    return mapa


@jwt_required()
def list_camera_modules():  # type: ignore[no-untyped-def]
    """GET /api/cameras/modules — tudo que a tela de atribuição precisa.

    Três coisas numa resposta só (câmeras, vínculos, módulos liberados) porque
    a tela precisa das três juntas para ser desenhada: com as câmeras sem os
    vínculos ela pintaria toda câmera como "sem módulo", que é uma afirmação
    falsa enquanto a segunda resposta não chega.

    Câmera ARQUIVADA vem na lista, com is_active=false: a tela precisa poder
    mostrá-la se o dono quiser: esconder câmera arquivada aqui faria o vínculo
    dela virar um dado invisível e não editável.
    """
    try:
        tenant_id = str(get_tenant_id())
        cameras = _get_camera_repo().get_by_user(UUID(tenant_id))
        vinculos = _mapa_de_vinculos(tenant_id)
        return success({
            "cameras": [
                {
                    "id": str(c["id"]),
                    "name": c["name"],
                    "location": c.get("location"),
                    "is_active": c["is_active"],
                    "modules": vinculos.get(str(c["id"]), []),
                }
                for c in cameras
            ],
            "modules_enabled": _modules_do_tenant(),
        })
    except Exception as exc:
        logger.error("list_camera_modules_error: %s", exc, exc_info=True)
        return error("Erro ao carregar câmeras e módulos", 500)


@require_permission("cameras:configure")
def put_camera_modules():  # type: ignore[no-untyped-def]
    """PUT /api/cameras/modules

    Body: {"camera_ids": ["<uuid>", ...], "modules": ["epi", "quality"]}

    `modules` passa a ser EXATAMENTE o conjunto de cada câmera listada — o que
    saiu é desmarcado, o que entrou é marcado, numa transação só.

    `modules: []` é válido e significa "não serve a módulo nenhum". Recusar a
    lista vazia obrigaria o dono a deixar uma marcação errada no lugar por
    falta de como tirá-la.
    """
    try:
        data = request.get_json() or {}
        camera_ids_cru = data.get("camera_ids")
        modules_cru = data.get("modules")

        if not isinstance(camera_ids_cru, list) or not camera_ids_cru:
            raise ValidationError("camera_ids é obrigatório e não pode ser vazio")
        if not isinstance(modules_cru, list):
            raise ValidationError("modules é obrigatório (lista, pode ser vazia)")
        if len(camera_ids_cru) > _MAX_CAMERAS_POR_CHAMADA:
            raise ValidationError(
                f"no máximo {_MAX_CAMERAS_POR_CHAMADA} câmeras por chamada"
            )

        # dict.fromkeys: tira repetido preservando a ordem — repetir a mesma
        # câmera no payload faria o executemany gravar a mesma linha 2x.
        camera_ids = list(dict.fromkeys(str(c) for c in camera_ids_cru))
        modules = list(dict.fromkeys(str(m).strip() for m in modules_cru))

        for cid in camera_ids:
            try:
                UUID(cid)
            except (ValueError, AttributeError, TypeError):
                raise ValidationError(f"camera_id inválido: {cid}") from None

        # Gate por tenant, fail-closed (mesma regra do PATCH .../module):
        # módulo que o tenant não tem não entra nem por payload montado à mão.
        for mod in modules:
            if not mod:
                raise ValidationError("módulo vazio na lista")
            if not _is_module_allowed(mod):
                raise AuthorizationError(
                    f"Módulo '{mod}' não habilitado para este tenant."
                )

        tenant_id = str(get_tenant_id())
        # C-01: câmera de outro tenant responde 404, nunca 403 — 403 confirmaria
        # que a câmera existe. Uma consulta só (a lista do tenant), não uma por
        # id: a ação em massa manda 29 de uma vez.
        do_tenant = {
            str(c["id"]) for c in _get_camera_repo().get_by_user(UUID(tenant_id))
        }
        for cid in camera_ids:
            if cid not in do_tenant:
                raise NotFoundError("Câmera", cid)

        _get_link_repo().replace_for_cameras(
            tenant_id, camera_ids, modules, str(get_current_user_id())
        )

        logger.info(
            "camera_modules_updated: tenant=%s cameras=%d modules=%s",
            tenant_id, len(camera_ids), modules,
        )
        # Devolve o estado GRAVADO (releitura), não o payload ecoado: se o
        # banco divergir do que foi pedido, a tela tem de mostrar o banco.
        vinculos = _mapa_de_vinculos(tenant_id)
        gravado: dict[str, Any] = {cid: vinculos.get(cid, []) for cid in camera_ids}
        return success({"assignments": gravado})

    except (NotFoundError, ValidationError, AuthorizationError):
        raise
    except Exception as exc:
        logger.error("put_camera_modules_error: %s", exc, exc_info=True)
        return error("Erro ao salvar os módulos das câmeras", 500)
