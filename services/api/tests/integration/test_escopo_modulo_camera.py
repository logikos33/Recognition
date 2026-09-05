"""Escopo de módulo por câmera (public.camera_modules, migration 134).

RÉGUA COM MUTAÇÃO — o que estes testes provam, e como se prova que provam.

O predicado único vive em `camera_module_repository.escopo_sql` /
`escopo_camera_sql`. Desarmar o filtro é trocar o corpo de `_ESCOPO_SQL` por
`"({col} IS NOT NULL OR TRUE)"` (e o de `_ESCOPO_CAMERA_SQL` por
`"({mod_col} = %s OR TRUE)"`, mantendo os %s). Rodado assim:

    test_pool_de_anotacao_nao_serve_frame_de_camera_fora_do_modulo  FALHA
    test_dashboard_nao_conta_camera_fora_do_modulo                  FALHA
    test_fila_de_incerteza_nao_serve_frame_de_camera_fora_do_modulo FALHA
    test_eventos_do_modulo_nao_contam_camera_fora_do_modulo         FALHA

Os testes de "escopo não declarado" continuam PASSANDO com o filtro desarmado
— e é exatamente o que se espera deles: eles guardam o comportamento de HOJE
(tabela vazia = nada muda), não o filtro. São a rede que impede alguém de
"consertar" o filtro de um jeito que zere a galeria de todo mundo no deploy.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.database.repositories.camera_module_repository import (
    CameraModuleRepository,
)
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.frame_repository import FrameRepository


# ---------------------------------------------------------------------------
# Cenário: duas câmeras no mesmo tenant, uma frame em cada.
# ---------------------------------------------------------------------------

@pytest.fixture
def cenario(pg_raw, tenant_id):
    """Tenant com 2 câmeras (uma "de EPI", outra "de estacionamento"), 1 frame
    em cada, 1 alerta em cada. NENHUM vínculo declarado ainda — é o estado do
    banco no instante do deploy da migration 134.
    """
    user = str(uuid4())
    cam_epi = str(uuid4())
    cam_fora = str(uuid4())
    frame_epi = str(uuid4())
    frame_fora = str(uuid4())
    agora = datetime.now(tz=timezone.utc)

    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
            "VALUES (%s, %s, 'x', 'IntTest', 'admin', %s)",
            (user, f"esc-{user[:8]}@test.dev", tenant_id),
        )
        for cid, nome in ((cam_epi, "Corredor Segurança"), (cam_fora, "Guarita")):
            cur.execute(
                "INSERT INTO public.cameras "
                "(id, tenant_id, user_id, name, host, module_code, active_module, is_active) "
                "VALUES (%s, %s, %s, %s, '10.0.0.1', 'epi', 'epi', true)",
                (cid, tenant_id, user, nome),
            )
        for fid, cid in ((frame_epi, cam_epi), (frame_fora, cam_fora)):
            cur.execute(
                "INSERT INTO public.training_frames "
                "(id, frame_number, filename, source, camera_id, tenant_id, "
                " module_code, r2_key, is_annotated, curation_status) "
                "VALUES (%s, 0, %s, 'nvr', %s, %s, 'epi', %s, false, 'active')",
                (fid, f"{fid}.jpg", cid, tenant_id, f"k/{fid}.jpg"),
            )
        for cid in (cam_epi, cam_fora):
            cur.execute(
                "INSERT INTO public.alerts "
                "(id, camera_id, tenant_id, module_code, timestamp, violations, "
                " confidence, created_at) "
                "VALUES (%s, %s, %s, 'epi', %s, '[]'::jsonb, 0.9, %s)",
                (str(uuid4()), cid, tenant_id, agora, agora),
            )

    yield {
        "user": user,
        "cam_epi": cam_epi,
        "cam_fora": cam_fora,
        "frame_epi": frame_epi,
        "frame_fora": frame_fora,
        "agora": agora,
    }

    # Ordem reversa das FKs — o tenant só some depois dos filhos (a fixture
    # `tenant_id` do conftest faz o DELETE do tenant e não conhece o user).
    with pg_raw.cursor() as cur:
        cur.execute(
            "DELETE FROM public.training_frames WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute("DELETE FROM public.alerts WHERE tenant_id = %s", (tenant_id,))
        cur.execute(
            "DELETE FROM public.camera_modules WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute("DELETE FROM public.cameras WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM public.users WHERE tenant_id = %s", (tenant_id,))


def _declara_epi(pg_raw, tenant_id: str, camera_id: str) -> None:
    """O dono marca UMA câmera como EPI na tela de atribuição."""
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.camera_modules "
            "(tenant_id, camera_id, module_code, enabled) "
            "VALUES (%s, %s, 'epi', true)",
            (tenant_id, camera_id),
        )


# ---------------------------------------------------------------------------
# (a) POOL DE ANOTAÇÃO
# ---------------------------------------------------------------------------

def test_pool_de_anotacao_nao_serve_frame_de_camera_fora_do_modulo(
    pg_pool, pg_raw, tenant_id, cenario
):
    """RÉGUA COM MUTAÇÃO — o teste que tem de ficar VERMELHO sem o filtro.

    O dono declarou só a câmera de EPI. O frame da Guarita continua no banco
    (nada é apagado), mas não pode aparecer no pool de anotação do EPI.
    """
    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])
    repo = FrameRepository(pg_pool)

    resultado = repo.list_images_filtered(tenant_id=tenant_id, module_code="epi")
    ids = {str(f["id"]) for f in resultado["frames"]}

    assert cenario["frame_epi"] in ids
    assert cenario["frame_fora"] not in ids, (
        "frame de câmera SEM vínculo EPI entrou no pool de anotação do EPI"
    )
    assert resultado["total"] == 1
    # A contagem do que foi filtrado sai no RESULTADO, não só no log — foi o
    # silêncio de um filtro que custou 1.098 anotações nesta casa.
    assert resultado["fora_do_modulo"] == 1

    # ⛔ e o frame NÃO foi apagado: continua lá, esperando o dono decidir.
    with pg_raw.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM public.training_frames WHERE id = %s",
            (cenario["frame_fora"],),
        )
        assert cur.fetchone()["n"] == 1


def test_pool_sem_vinculo_declarado_serve_tudo(pg_pool, tenant_id, cenario):
    """Escopo NÃO declarado não filtra nada.

    Este é o teste que impede o "conserto" que zera a galeria de todos os
    tenants no dia do deploy: a tabela 134 nasce vazia e sem backfill.
    """
    repo = FrameRepository(pg_pool)
    resultado = repo.list_images_filtered(tenant_id=tenant_id, module_code="epi")

    assert resultado["total"] == 2
    assert resultado["fora_do_modulo"] == 0


def test_pool_ignora_camera_desmarcada(pg_pool, pg_raw, tenant_id, cenario):
    """Desmarcar é UPDATE enabled=false — e uma linha desmarcada não vale
    como vínculo NEM como "escopo declarado"."""
    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])
    with pg_raw.cursor() as cur:
        cur.execute(
            "UPDATE public.camera_modules SET enabled = false "
            "WHERE tenant_id = %s AND camera_id = %s",
            (tenant_id, cenario["cam_epi"]),
        )

    resultado = FrameRepository(pg_pool).list_images_filtered(
        tenant_id=tenant_id, module_code="epi"
    )
    # Nenhum vínculo ATIVO no módulo → escopo volta a não estar declarado.
    assert resultado["total"] == 2
    assert resultado["fora_do_modulo"] == 0


def test_frame_sem_camera_nunca_e_filtrado(pg_pool, pg_raw, tenant_id, cenario):
    """Upload manual e frame de vídeo não têm câmera — o escopo não pode
    engoli-los junto."""
    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])
    sem_cam = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.training_frames "
            "(id, frame_number, filename, source, camera_id, tenant_id, "
            " module_code, r2_key, is_annotated, curation_status) "
            "VALUES (%s, 0, %s, 'upload', NULL, %s, 'epi', %s, false, 'active')",
            (sem_cam, f"{sem_cam}.jpg", tenant_id, f"k/{sem_cam}.jpg"),
        )

    resultado = FrameRepository(pg_pool).list_images_filtered(
        tenant_id=tenant_id, module_code="epi"
    )
    assert sem_cam in {str(f["id"]) for f in resultado["frames"]}


def test_fila_de_incerteza_nao_serve_frame_de_camera_fora_do_modulo(
    pg_pool, pg_raw, tenant_id, cenario
):
    """A fila de aprendizado ativo (aba Classificar / active learning) é outra
    porta para o mesmo pool — e tem de respeitar o mesmo escopo."""
    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])
    frames = FrameRepository(pg_pool).list_unlabeled_by_uncertainty(
        tenant_id, "epi", limit=50
    )
    ids = {str(f["id"]) for f in frames}

    assert cenario["frame_epi"] in ids
    assert cenario["frame_fora"] not in ids


# ---------------------------------------------------------------------------
# (b) DASHBOARD / EVENTOS
# ---------------------------------------------------------------------------

def test_dashboard_nao_conta_camera_fora_do_modulo(
    pg_pool, pg_raw, tenant_id, cenario
):
    """RÉGUA COM MUTAÇÃO — KPI "câmeras do módulo".

    As duas câmeras têm module_code='epi' no banco, porque 'epi' é o DEFAULT
    da coluna. Depois que o dono declara uma, o KPI tem de dizer 1, não 2.
    """
    repo = CameraRepository(pg_pool)
    assert repo.count_by_module(tenant_id, "epi") == 2  # antes de declarar

    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])

    assert repo.count_by_module(tenant_id, "epi") == 1, (
        "câmera SEM vínculo EPI continuou contando no KPI do módulo EPI"
    )
    assert repo.count_by_status(tenant_id, "epi", "active") == 1


def test_dashboard_conta_camera_vinculada_mesmo_com_coluna_divergente(
    pg_pool, pg_raw, tenant_id, cenario
):
    """O vínculo SUBSTITUI a coluna legada, não soma a ela.

    Sem isso, uma câmera que o dono acabou de vincular ao EPI sumiria do KPI
    só porque `cameras.module_code` ainda diz outra coisa — e não haveria como
    consertar pela tela nova.
    """
    with pg_raw.cursor() as cur:
        cur.execute(
            "UPDATE public.cameras SET module_code = 'quality' WHERE id = %s",
            (cenario["cam_epi"],),
        )
    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])

    assert CameraRepository(pg_pool).count_by_module(tenant_id, "epi") == 1


def test_eventos_do_modulo_nao_contam_camera_fora_do_modulo(
    pg_pool, pg_raw, tenant_id, cenario
):
    """Alertas: os dois eventos estão carimbados module_code='epi' (herdado do
    default de active_module). Só o da câmera declarada conta."""
    repo = AlertRepository(pg_pool)
    desde = cenario["agora"] - timedelta(hours=1)

    assert repo.count_since(tenant_id, "epi", desde) == 2  # antes de declarar

    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])

    assert repo.count_since(tenant_id, "epi", desde) == 1, (
        "alerta de câmera SEM vínculo EPI continuou no KPI do módulo EPI"
    )
    assert repo.count_in_window(
        tenant_id, desde, cenario["agora"] + timedelta(hours=1), "epi"
    ) == 1

    busca = repo.search_events(tenant_id, module_code="epi", include_demo=False)
    assert busca["total"] == 1
    assert {str(e["camera_id"]) for e in busca["items"]} == {cenario["cam_epi"]}


# ---------------------------------------------------------------------------
# (a)/(c) O PORTÃO DE UMA CÂMERA SÓ — ingestão e deployment de modelo
# ---------------------------------------------------------------------------

def test_camera_serves_module_e_o_mesmo_veredito_do_predicado(
    pg_pool, pg_raw, tenant_id, cenario
):
    """`camera_serves_module` (ingestão e escrita de modelo) tem de concordar
    com `escopo_sql` (leituras) — duas respostas diferentes para a mesma
    pergunta seria o pior desfecho possível deste desenho."""
    repo = CameraModuleRepository(pg_pool)

    # escopo não declarado: TUDO passa (coleta não pode parar no deploy)
    assert repo.camera_serves_module(tenant_id, cenario["cam_epi"], "epi") is True
    assert repo.camera_serves_module(tenant_id, cenario["cam_fora"], "epi") is True

    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])

    assert repo.camera_serves_module(tenant_id, cenario["cam_epi"], "epi") is True
    assert repo.camera_serves_module(tenant_id, cenario["cam_fora"], "epi") is False
    # Outro módulo, sem nenhum vínculo declarado → segue liberado.
    assert repo.camera_serves_module(tenant_id, cenario["cam_fora"], "quality") is True


def test_vinculo_e_muitos_para_muitos(pg_pool, pg_raw, tenant_id, cenario):
    """A MESMA câmera pode servir EPI e Qualidade — é o pedido do dono, e o
    caso real da RVB ("Qualidade 01 EPI"). Uma coluna VARCHAR não faz isso."""
    repo = CameraModuleRepository(pg_pool)
    repo.replace_for_cameras(
        tenant_id, [cenario["cam_epi"]], ["epi", "quality"], cenario["user"]
    )

    assert repo.camera_serves_module(tenant_id, cenario["cam_epi"], "epi") is True
    assert repo.camera_serves_module(tenant_id, cenario["cam_epi"], "quality") is True
    # E a outra câmera, agora que os dois módulos têm escopo declarado, sai dos dois.
    assert repo.camera_serves_module(tenant_id, cenario["cam_fora"], "epi") is False
    assert repo.camera_serves_module(tenant_id, cenario["cam_fora"], "quality") is False


def test_facetas_batem_com_a_galeria(pg_pool, pg_raw, tenant_id, cenario):
    """A barra lateral não pode anunciar frame que a galeria não entrega.

    Divergência entre faceta e galeria é a receita do "a tela diz 2, mostra 1"
    — e o anotador passa a procurar material que aquele filtro nunca vai servir.
    """
    _declara_epi(pg_raw, tenant_id, cenario["cam_epi"])
    repo = FrameRepository(pg_pool)

    galeria = repo.list_images_filtered(tenant_id=tenant_id, module_code="epi")
    facetas = repo.get_facets(tenant_id=tenant_id, module_code="epi")

    total_facetas = sum(c["count"] for c in facetas["cameras"])
    assert total_facetas == galeria["total"] == 1
    assert {str(c["camera_id"]) for c in facetas["cameras"]} == {cenario["cam_epi"]}
