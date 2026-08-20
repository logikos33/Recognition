"""Integracao: a FILA DA ANOTACAO nunca devolve recorte ja processado.

Dois defeitos de campo, os dois medidos no acervo real do RVB antes de
qualquer edicao (7.081 recortes, DEV):

1. **Fixture com os tres**: excluida, duvida e ja-anotado nao podem sair da
   fila. O predicado existe em list_images_filtered desde a migration 110 —
   este teste o PRENDE, com dado real em Postgres real, em vez de assertar
   texto de SQL.

2. **Deriva do OFFSET**: a fila ENCOLHE enquanto e percorrida (cada veredito
   tira o frame do conjunto). Com `OFFSET n*page_size` a janela escorrega
   sobre um conjunto de outro tamanho e o que fica entre um lote e o proximo
   NUNCA e mostrado — 3.521 dos 7.081 (49,7%) no acervo do RVB, com a tela
   ainda anunciando "fila concluida". O cursor keyset nao escorrega.

Falha-antes/passa-depois do (2): com paginacao por OFFSET o teste perde
recortes; com cursor, mostra todos.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.frame_repository import FrameRepository

# Dimensoes unicas por frame: `only_crops` descarta (width, height) repetida
# >= _FULL_FRAME_MIN_REPEATS vezes (heuristica de "frame inteiro"). Aqui todo
# frame e recorte, entao cada um ganha o seu par.
_BASE = datetime(2026, 8, 1, 12, 0, 0)


@pytest.fixture
def tenant(pg_raw):  # type: ignore[no-untyped-def]
    tid = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (tid, f"FilaTest {tid[:8]}", f"fila-{tid[:8]}"),
        )
    yield tid
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.training_frames WHERE tenant_id = %s", (tid,))
        cur.execute("DELETE FROM public.tenants WHERE id = %s", (tid,))


def _inserir(pg_raw, tenant_id, n, *, curation="active", annotated=False, offset=0):
    """N frames com created_at decrescente e dimensao unica (= recorte)."""
    ids = []
    with pg_raw.cursor() as cur:
        for i in range(n):
            fid = str(uuid4())
            k = offset + i
            cur.execute(
                "INSERT INTO public.training_frames "
                "(id, video_id, frame_number, filename, source, r2_key, tenant_id, "
                " width, height, curation_status, is_annotated, created_at) "
                "VALUES (%s, NULL, %s, %s, 'nvr', %s, %s, %s, %s, %s, %s, %s)",
                (fid, k, f"{fid}.jpg", f"t/{tenant_id}/{fid}.jpg", tenant_id,
                 100 + k, 200 + k, curation, annotated, _BASE - timedelta(seconds=k)),
            )
            ids.append(fid)
    return ids


def _fila(repo, tenant_id, *, page=1, cursor=None, page_size=10):
    """Os MESMOS filtros que a aba Classificar manda (CropClassifier.tsx)."""
    return repo.list_images_filtered(
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        is_annotated=False,
        curation_status="active",
        only_crops=True,
        cursor=cursor,
    )


class TestFilaNuncaDevolveProcessado:
    def test_excluida_duvida_e_ja_anotado_ficam_de_fora(self, pg_pool, pg_raw, tenant):
        repo = FrameRepository(pg_pool)
        ativos = set(_inserir(pg_raw, tenant, 3, offset=0))
        excluidos = set(_inserir(pg_raw, tenant, 2, curation="excluida", offset=10))
        duvidas = set(_inserir(pg_raw, tenant, 2, curation="duvida", offset=20))
        anotados = set(_inserir(pg_raw, tenant, 2, annotated=True, offset=30))

        devolvidos = {str(f["id"]) for f in _fila(repo, tenant)["frames"]}

        assert devolvidos == ativos
        assert devolvidos & excluidos == set()
        assert devolvidos & duvidas == set()
        assert devolvidos & anotados == set()


class TestCursorNaoEscorrega:
    def test_offset_perde_recortes_quando_a_fila_encolhe(self, pg_pool, pg_raw, tenant):
        """O defeito, exposto: paginar por OFFSET enquanto se anota."""
        repo = FrameRepository(pg_pool)
        todos = set(_inserir(pg_raw, tenant, 30))
        LOTE = 10

        vistos: set = set()
        pagina = 1
        while True:
            frames = _fila(repo, tenant, page=pagina, page_size=LOTE)["frames"]
            if not frames:
                break
            for f in frames:
                fid = str(f["id"])
                vistos.add(fid)
                # veredito: sai do conjunto, como curadoria/anotacao fazem
                with pg_raw.cursor() as cur:
                    cur.execute(
                        "UPDATE public.training_frames SET curation_status = 'excluida' "
                        "WHERE id = %s",
                        (fid,),
                    )
            pagina += 1

        # 🔴 o defeito: a janela escorregou e sobrou material invisivel
        assert vistos != todos
        assert len(todos - vistos) > 0

    def test_cursor_mostra_o_acervo_INTEIRO(self, pg_pool, pg_raw, tenant):
        """Mesmo laco, mesma escrita, cursor no lugar do OFFSET."""
        repo = FrameRepository(pg_pool)
        todos = set(_inserir(pg_raw, tenant, 30))
        LOTE = 10

        vistos: set = set()
        cursor = None
        while True:
            frames = _fila(repo, tenant, cursor=cursor, page_size=LOTE)["frames"]
            if not frames:
                break
            ultimo = frames[-1]
            cursor = (ultimo["created_at"], str(ultimo["id"]))
            for f in frames:
                fid = str(f["id"])
                vistos.add(fid)
                with pg_raw.cursor() as cur:
                    cur.execute(
                        "UPDATE public.training_frames SET curation_status = 'excluida' "
                        "WHERE id = %s",
                        (fid,),
                    )

        assert vistos == todos, f"faltaram {len(todos - vistos)} recortes"

    def test_cursor_nunca_repete_entre_lotes(self, pg_pool, pg_raw, tenant):
        repo = FrameRepository(pg_pool)
        _inserir(pg_raw, tenant, 25)
        p1 = _fila(repo, tenant, page_size=10)["frames"]
        c1 = (p1[-1]["created_at"], str(p1[-1]["id"]))
        p2 = _fila(repo, tenant, cursor=c1, page_size=10)["frames"]
        c2 = (p2[-1]["created_at"], str(p2[-1]["id"]))
        p3 = _fila(repo, tenant, cursor=c2, page_size=10)["frames"]

        ids1 = {str(f["id"]) for f in p1}
        ids2 = {str(f["id"]) for f in p2}
        ids3 = {str(f["id"]) for f in p3}
        assert ids1 & ids2 == set()
        assert ids2 & ids3 == set()
        assert ids1 & ids3 == set()
        assert len(ids1 | ids2 | ids3) == 25
