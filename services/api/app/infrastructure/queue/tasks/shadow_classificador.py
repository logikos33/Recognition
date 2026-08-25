"""Caminho 2 da ADR-0067 em SHADOW: recorte → veredito → evento.

═══ POR QUE ESTA TAREFA EXISTE, E NÃO O `inference_loop` ═══

`inference_loop` lê RTSP com `cap.read()`. RTSP das câmeras do RVB só existe
dentro da rede do cliente (MikroTik + WireGuard, ADR-0020) — a nuvem não
alcança. Medido: `inference_loop` **não tem chamador de produção** no repo; o
único despacho é o console de teste do admin.

O que EXISTE e está vivo é o outro lado: o coletor do edge sobe recortes de
pessoa para o pool. Medido em 25/08: **12.053 frames NVR**, o mais novo de
hoje 06:40, ~2.500 recortes ainda não julgados em 10 câmeras.

E o estágio 1 da ADR-0067 já está feito nesses frames: `crop_person()` roda no
edge ANTES do upload, com YOLOX-nano ladrilhado (recall de pessoa 52%→90%
medido em 40 frames reais). **O que o edge sobe já é o recorte da pessoa.**

Então o caminho 2 servido, nesta arquitetura, é sobre o recorte que chega —
não sobre um stream que a nuvem não vê.

═══ SHADOW ═══

⛔ ZERO notificação. Não existe despachante de notificação no repo (conferido:
não há `tasks/notification*.py`; `NotificationRepository` só é usado pela
própria rota REST). O evento nasce e fica no dashboard. Este é o contrato desta
rodada e está fixado em teste.

═══ AS QUATRO CONDIÇÕES DA ADR-0067 ═══

Uma violação só nasce com TODAS:

  1. veredito `sem` do classificador de recorte;
  2. confiança ≥ limiar da família (senão: abstenção);
  3. classe que PASSOU a régua no campo virgem (a medida viaja no artefato);
  4. dentro da ZONA onde aquele EPI é exigido.

E depois disso ainda passa pela persistência temporal — veredito num frame não
é violação.

`nao_visivel` é abstenção, jamais violação.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

#: Nome de classe do evento, por família e veredito. Tem de bater com o que o
#: cadastro do tenant conhece (yolo_classes / module_classes) — senão a
#: polaridade não resolve e o evento vira "classe sem polaridade".
CLASSE_DO_VEREDITO = {
    ("mascara", "sem"): "Sem mascara",
    ("mascara", "incorreto"): "Uso incorreto de mascara",
    ("mascara", "com"): "mascara",
    ("luvas", "sem"): "Sem Luvas",
    ("luvas", "com"): "Luvas",
    ("oculos", "sem"): "Sem Óculos",
    ("oculos", "com"): "Óculos",
    ("auditiva", "sem"): "Sem protetor de ouvido",
    ("auditiva", "com"): "Protetor auditivo",
}


def _zonas_da_camera(pool, tenant_id: str, camera_id: str) -> set[str] | None:
    """Classes exigidas nesta câmera, da união das zonas EPI configuradas.

    `None` = nenhuma zona configurada. E aí a decisão é do desenho: **sem zona,
    nada alerta**. A ADR-0067 exige "na zona onde o EPI é exigido", e tratar
    ausência de zona como "exigido em todo lugar" seria inventar requisito que
    ninguém declarou — exatamente o oposto do que a ADR decidiu.

    Isso torna o shadow explicitamente opt-in por câmera: configurar a zona é
    o ato de ligar.

    ⚠️ **O POLÍGONO não é aplicado aqui, e não escondo isso.** O frame que o
    edge sobe JÁ é o recorte da pessoa, e nada registra onde aquele recorte
    ficava no frame original (`training_frames` não tem bbox de origem —
    conferido nas 129 migrations). Sem coordenada, não há como dizer se a
    pessoa estava dentro do polígono.

    O que ESTÁ sendo usado da zona é o `watch_classes`: **qual EPI é exigido
    NESTA câmera**. É a metade que importa hoje, e é exatamente a metade que a
    matriz do Paulo (#535) vai preencher. Aplicar o polígono de verdade exige
    gravar a caixa de origem do recorte — registrado como dívida.
    """
    from app.infrastructure.database.repositories.base import (  # noqa: PLC0415
        BaseRepository,
    )

    try:
        linhas = BaseRepository(pool)._execute(  # noqa: SLF001
            "SELECT config FROM operations "
            " WHERE tenant_id = %s AND camera_id = %s AND type_id = 'epi_zone' "
            "   AND status <> 'inactive'",
            (str(tenant_id), str(camera_id)),
        )
    except Exception as exc:
        logger.warning(
            "zonas_leitura_falhou: camera=%s err=%s — sem zona, nada alerta",
            camera_id, exc,
        )
        return None

    exigidas: set[str] = set()
    for linha in linhas:
        cfg = linha.get("config") or {}
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except Exception:  # noqa: BLE001
                continue
        for c in cfg.get("watch_classes") or []:
            exigidas.add(str(c).strip().lower())
    return exigidas or None


def _redis():
    import redis  # noqa: PLC0415

    import os  # noqa: PLC0415

    return redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"), decode_responses=True
    )


def _grava_evento(pool, tenant_id: str, frame: dict, classe: str, v: dict) -> bool:
    """Grava o evento pelo MESMO repositório do caminho de alerta.

    ⛔ SHADOW: grava e para. Não há despachante de notificação no repo — o
    evento nasce visível só no dashboard, que é o contrato desta rodada.

    A EVIDÊNCIA é o recorte, e é honesto dizer isso: o frame que o edge subiu
    JÁ é o recorte da pessoa, e o frame inteiro original não está guardado em
    lugar nenhum. Então "frame inteiro" e "caixa da pessoa" coincidem aqui —
    a caixa é [0,0,w,h] do próprio recorte. Prometer um frame de contexto que
    não existe seria mentir na tela de evidência.
    """
    from app.infrastructure.database.repositories.alert_repository import (  # noqa: PLC0415
        AlertRepository,
    )

    try:
        AlertRepository(pool).create(
            camera_id=frame["camera_id"],
            violations=[{
                "class": classe,
                "confidence": v["confianca"],
                # O recorte É a pessoa: a caixa cobre o recorte inteiro.
                "bbox": [0, 0, 0, 0],
                "bbox_unidade": "recorte_da_pessoa_sem_coordenada_no_frame_original",
                "origem": "classificador_recorte_v1",
                "veredito": v["veredito"],
                "motivo": v["motivo"],
            }],
            confidence=v["confianca"],
            evidence_key=frame["r2_key"],
            tenant_id=str(tenant_id),
            module_code="epi",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("shadow_gravar_evento_falhou: frame=%s err=%s", frame["id"], exc)
        return False


@celery.task(name="tasks.shadow_classificador.passada_shadow", bind=True)
def passada_shadow(  # noqa: ANN001, PLR0913
    self,
    tenant_id: str,
    limite: int = 200,
    camera_id: str | None = None,
    gravar_eventos: bool = False,
) -> dict:
    """Julga recortes do pool e (opcionalmente) grava os eventos.

    `gravar_eventos=False` por padrão — a passada em modo LEITURA devolve as
    contagens sem tocar em `alerts`. É como se mede antes de ligar, e é o que
    permite responder "quantos eventos isto geraria?" sem gerar nenhum.
    """
    from app.domain.detectors.classificador_recorte import (  # noqa: PLC0415
        classificador_do_tenant,
    )
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.base import (  # noqa: PLC0415
        BaseRepository,
    )
    from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

    pool = DatabasePool.get_instance()
    if pool is None:
        return {"status": "erro", "motivo": "sem pool"}

    clf = classificador_do_tenant(tenant_id)
    if clf is None:
        # ABSTENÇÃO, não silêncio: sem classificador não há veredito, e isso
        # é diferente de "ninguém violou nada".
        logger.error("shadow_sem_classificador: tenant=%s", tenant_id)
        return {"status": "abstido", "motivo": "classificador não carregou"}

    repo = BaseRepository(pool)
    filtro_cam = " AND tf.camera_id = %s" if camera_id else ""
    params: tuple[Any, ...] = (
        (str(tenant_id), str(camera_id), limite)
        if camera_id
        else (str(tenant_id), limite)
    )
    frames = repo._execute(  # noqa: SLF001, S608 — filtro de coluna fixa, valor parametrizado
        "SELECT tf.id, tf.r2_key, tf.camera_id, COALESCE(c.name,'?') AS camera "
        "  FROM training_frames tf "
        "  LEFT JOIN cameras c ON c.id = tf.camera_id "
        f" WHERE tf.tenant_id = %s AND tf.source = 'nvr' {filtro_cam} "
        "   AND tf.is_annotated IS NOT TRUE "
        "   AND COALESCE(tf.curation_status,'') <> 'excluida' "
        "   AND tf.r2_key IS NOT NULL "
        " ORDER BY tf.created_at DESC LIMIT %s",
        params,
    )

    armazenamento = get_storage(tenant_id)
    zonas_por_camera: dict[str, set[str] | None] = {}
    contagem: dict[str, int] = {}
    abstencoes = 0
    fora_de_zona = 0
    aguardando = 0
    gravados = 0
    evidencias: list[dict] = []
    julgados = 0

    for f in frames:
        try:
            imagem = armazenamento.download_bytes(f["r2_key"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("shadow_frame_ilegivel: %s err=%s", f["id"], exc)
            continue
        vereditos = clf.julgar(imagem)
        if not vereditos:
            continue
        julgados += 1

        cam = str(f["camera_id"]) if f["camera_id"] else ""
        if cam not in zonas_por_camera:
            zonas_por_camera[cam] = _zonas_da_camera(pool, tenant_id, cam) if cam else None
        exigidas = zonas_por_camera[cam]

        for familia, v in vereditos.items():
            if v["veredito"] == "nao_visivel":
                abstencoes += 1
                continue
            classe = CLASSE_DO_VEREDITO.get((familia, v["veredito"]))
            if not classe:
                continue
            chave = f"{f['camera']} · {classe}"
            if not v["pode_alertar"]:
                contagem[f"conformidade · {classe}"] = (
                    contagem.get(f"conformidade · {classe}", 0) + 1
                )
                continue
            # 4ª condição da ADR-0067: dentro da zona onde o EPI é exigido
            if exigidas is None or classe.lower() not in exigidas:
                fora_de_zona += 1
                continue
            # PERSISTÊNCIA TEMPORAL (ADR-0067): veredito num recorte não é
            # violação. Só grava quando a classe se sustenta na janela da
            # regra cadastrada. Sem regra, uma ocorrência basta — o
            # comportamento de sempre.
            if gravar_eventos:
                from app.infrastructure.queue.tasks.inference import (  # noqa: PLC0415
                    _persistencia_satisfeita,
                )

                sustentou = _persistencia_satisfeita(
                    cam, [{"class": classe}], _redis()
                )
                if not sustentou:
                    aguardando += 1
                    continue
                if _grava_evento(pool, tenant_id, f, classe, v):
                    gravados += 1

            contagem[chave] = contagem.get(chave, 0) + 1
            if len(evidencias) < 3:
                evidencias.append({
                    "frame_id": str(f["id"]), "r2_key": f["r2_key"],
                    "camera": f["camera"], "classe": classe,
                    "veredito": v["veredito"], "confianca": v["confianca"],
                    "motivo": v["motivo"],
                })

    resultado = {
        "status": "ok",
        "frames_lidos": len(frames),
        "frames_julgados": julgados,
        "abstencoes": abstencoes,
        "fora_de_zona": fora_de_zona,
        "aguardando_persistencia": aguardando,
        "eventos_gravados": gravados,
        "contagem": contagem,
        "evidencias": evidencias,
        "gravou_eventos": bool(gravar_eventos),
    }
    logger.info("shadow_passada: %s", json.dumps(resultado, ensure_ascii=False)[:600])
    return resultado
