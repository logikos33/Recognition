"""Handlers: a triagem do gabarito — a régua do A/B das variantes de detector.

O QUE ESTA FILA É, E O QUE ELA NÃO É

`scripts/ops/ab_ausencia.py` compara as três variantes no nível da DECISÃO:
"por imagem e por classe de ausência, o modelo ACUSOU ou não, e o gabarito diz
se aquela ausência era real". Logo o gabarito é uma resposta POR IMAGEM — o
avaliador não desenha caixa nenhuma.

Isso não é uma simplificação da interface, é o que a prova precisa. Caixa só
serve para TREINAR, e estes quadros são `dataset_role='holdout'` (migration
133): eles nunca entram em treino, por allowlist no export. Pedir geometria
aqui produziria dado que ninguém consome — e produzi-lo num celular, sobre
quadro 1920x1080, produziria dado ERRADO.

⛔ O veredito NÃO vai para `frame_annotations`. Vai para
`public.holdout_verdicts` (migration 135), que nenhuma query de export de
treino conhece. Ver o cabeçalho da migration e de `gabarito_repository.py`.
"""
import logging

from flask import request
from flask_jwt_extended import get_jwt_identity

from app.constants import (
    GABARITO_CLASSES,
    GABARITO_CLASSES_FOCO,
    HoldoutVerdict,
    HoldoutVerdictReason,
)
from app.core.auth import get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.domain.services.module_service import ModuleService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.gabarito_repository import (
    GabaritoRepository,
)
from app.infrastructure.storage.local_storage import get_storage
from app.infrastructure.storage.r2_storage import R2Storage

logger = logging.getLogger(__name__)

_VEREDITOS_VALIDOS = {v.value for v in HoldoutVerdict}


def _get_repo() -> GabaritoRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return GabaritoRepository(pool)


def _classes_do_gabarito(module_code: str, tenant_id: str) -> list[dict]:
    """As classes julgadas, resolvidas por NOME na lista unificada.

    `ModuleService.get_classes(module, tenant)` já une catálogo global e
    classes do tenant com o class_id no MESMO espaço de inteiros que o resto
    da pipeline usa (namespacing +100000 para as do tenant). Resolver por nome
    aqui é o que impede a régua de ficar presa aos ids que o DEV tem hoje.

    Classe da lista que não existir no ambiente simplesmente não aparece — a
    tela julga o que existe em vez de oferecer botão que não grava. `foco`
    viaja junto porque a hierarquia entre as classes é informação do produto
    (duas com gabarito zero travam o A/B), não decoração da tela.
    """
    disponiveis = {
        str(c.get("display_name") or c.get("class_name")): c
        for c in ModuleService().get_classes(module_code, tenant_id=tenant_id)
    }
    resolvidas = []
    for nome in GABARITO_CLASSES:
        classe = disponiveis.get(nome)
        if classe is None:
            logger.warning(
                "gabarito_classe_ausente: nome=%r module=%s — fora da triagem",
                nome,
                module_code,
            )
            continue
        resolvidas.append(
            {
                "class_id": int(classe["class_id"]),
                "nome": nome,
                "foco": nome in GABARITO_CLASSES_FOCO,
            }
        )
    return resolvidas


def get_gabarito_fila_handler():
    """A fila inteira do gabarito, de uma vez.

    Query: module (default 'epi').
    Resposta: success({classes, frames, total}).

    UMA requisição para a fila toda (~150 quadros) em vez de página por
    página: quem vai anotar está em rede móvel, e uma fila paginada faz a
    tela parar de funcionar exatamente quando o sinal cai. Baixada uma vez,
    ela vira o material de trabalho do aparelho.

    Cada quadro traz os vereditos JÁ DADOS (`verdicts`) — é assim que reabrir
    a mesma imagem mostra a resposta anterior em vez de uma tela em branco.

    `url` é presignada do R2: a tag <img> não manda Authorization, então o
    endpoint autenticado de bytes (/api/training/frames/<id>/image) daria 401
    nela. Mesmo padrão de list_training_images_handler.
    """
    try:
        tenant_id = get_tenant_id()
        module_code = request.args.get("module", "epi")
        frames = _get_repo().list_fila(str(tenant_id), module_code)

        storage = get_storage()
        if isinstance(storage, R2Storage):
            for frame in frames:
                try:
                    frame["url"] = storage.generate_presigned_download_url(
                        frame["filename"], ttl=3600, response_content_type="image/jpeg"
                    )
                except Exception as url_exc:  # noqa: BLE001
                    logger.warning(
                        "gabarito_presigned_url_failed frame=%s: %s",
                        frame.get("id"),
                        url_exc,
                    )
                    frame["url"] = None

        return success(
            {
                "classes": _classes_do_gabarito(module_code, str(tenant_id)),
                "frames": frames,
                "total": len(frames),
            }
        )
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_gabarito_fila_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def save_gabarito_verdicts_handler(frame_id: str):
    """Grava os vereditos de UM quadro. Sobrescreve os anteriores.

    Body: {"verdicts": {"<class_id>": "sim"|"nao"|"nao_sei", ...},
           "reason": "sem_pessoa" | null}

    404 para quadro inexistente, de outro tenant, ou que não é gabarito — as
    três respondem igual (C-01: 403 confirmaria que o id existe em algum
    lugar, e "não é holdout" confirmaria que existe neste tenant).

    O atalho "não há pessoa" não é um caminho separado no backend: ele chega
    como `nao` em todas as classes mais `reason='sem_pessoa'`. Um endpoint
    próprio para ele seria uma segunda forma de escrever o mesmo fato, e as
    duas divergiriam no dia em que alguém mudasse só uma.
    """
    try:
        tenant_id = get_tenant_id()
        body = request.get_json(silent=True) or {}
        brutos = body.get("verdicts")
        if not isinstance(brutos, dict) or not brutos:
            return error("verdicts é obrigatório e não pode ser vazio", 400)

        reason = body.get("reason")
        if reason is not None and reason != HoldoutVerdictReason.SEM_PESSOA.value:
            return error("reason inválido", 400)

        # Validação ANTES de qualquer escrita: veredito fora do domínio
        # gravaria lixo que o CHECK do banco rejeitaria com erro 500 — e um
        # class_id não-inteiro viraria exceção no meio da transação, deixando
        # metade das respostas do quadro no banco.
        verdicts: dict[int, str] = {}
        for class_id, verdict in brutos.items():
            try:
                chave = int(class_id)
            except (TypeError, ValueError):
                return error(f"class_id inválido: {class_id!r}", 400)
            if verdict not in _VEREDITOS_VALIDOS:
                return error(f"veredito inválido: {verdict!r}", 400)
            verdicts[chave] = verdict

        repo = _get_repo()
        if not repo.is_holdout_frame(str(frame_id), str(tenant_id)):
            return error("Quadro não encontrado", 404)

        gravados = repo.upsert_verdicts(
            frame_id=str(frame_id),
            tenant_id=str(tenant_id),
            verdicts=verdicts,
            judged_by=get_jwt_identity(),
            reason=reason,
        )
        return success({"frame_id": str(frame_id), "gravados": gravados})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("save_gabarito_verdicts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
