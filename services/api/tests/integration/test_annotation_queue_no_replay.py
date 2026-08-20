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
            cursor = str(frames[-1]["id"])
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
        p2 = _fila(repo, tenant, cursor=str(p1[-1]["id"]), page_size=10)["frames"]
        p3 = _fila(repo, tenant, cursor=str(p2[-1]["id"]), page_size=10)["frames"]

        ids1 = {str(f["id"]) for f in p1}
        ids2 = {str(f["id"]) for f in p2}
        ids3 = {str(f["id"]) for f in p3}
        assert ids1 & ids2 == set()
        assert ids2 & ids3 == set()
        assert ids1 & ids3 == set()
        assert len(ids1 | ids2 | ids3) == 25


class TestCursorEscopoEComportamento:
    """O escopo por tenant do cursor, medido em COMPORTAMENTO.

    O teste unitario irmao afirma sobre a STRING do SQL — prende o texto, nao
    o efeito. Aqui e Postgres real com dois tenants: uma reescrita que
    mantivesse a string mas perdesse o escopo passaria la e falha aqui.

    Por que o escopo importa: sem ele `before_id` viraria oraculo. Um id de
    outro tenant devolveria o `(created_at, id)` daquele frame, usado como
    fronteira sobre as SUAS linhas — contar quantas caem antes dela da busca
    binaria sobre o `created_at` de coleta de outro cliente. Nao vaza
    conteudo; vaza tempo. Com o escopo, id alheio e indistinguivel de id
    inexistente (C-01: nunca revele existencia).
    """

    def test_cursor_de_outro_tenant_nao_move_a_fila(self, pg_pool, pg_raw, tenant):
        repo = FrameRepository(pg_pool)
        _inserir(pg_raw, tenant, 10)

        outro = str(uuid4())
        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (outro, f"Outro {outro[:8]}", f"outro-{outro[:8]}"),
            )
        try:
            alheios = _inserir(pg_raw, outro, 3, offset=500)
            # cursor com id do OUTRO tenant -> fronteira NULL -> zero linhas,
            # exatamente como um id inexistente
            fr = _fila(repo, tenant, cursor=alheios[1], page_size=10)["frames"]
            assert fr == []

            inexistente = _fila(repo, tenant, cursor=str(uuid4()), page_size=10)["frames"]
            assert inexistente == []
        finally:
            with pg_raw.cursor() as cur:
                cur.execute("DELETE FROM public.training_frames WHERE tenant_id = %s", (outro,))
                cur.execute("DELETE FROM public.tenants WHERE id = %s", (outro,))

    def test_cursor_existe_e_escopado_por_tenant(self, pg_pool, pg_raw, tenant):
        """`cursor_frame_exists` — o que separa "cursor sumiu" de "acabou"."""
        repo = FrameRepository(pg_pool)
        ids = _inserir(pg_raw, tenant, 3)

        outro = str(uuid4())
        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (outro, f"Outro {outro[:8]}", f"outro-{outro[:8]}"),
            )
        try:
            alheios = _inserir(pg_raw, outro, 1, offset=600)
            assert repo.cursor_frame_exists(ids[0], tenant) is True
            assert repo.cursor_frame_exists(str(uuid4()), tenant) is False
            # id alheio == id inexistente: mesma resposta, sem revelar existencia
            assert repo.cursor_frame_exists(alheios[0], tenant) is False
        finally:
            with pg_raw.cursor() as cur:
                cur.execute("DELETE FROM public.training_frames WHERE tenant_id = %s", (outro,))
                cur.execute("DELETE FROM public.tenants WHERE id = %s", (outro,))

    def test_cursor_sobrevive_ao_frame_receber_veredito(self, pg_pool, pg_raw, tenant):
        """O frame-cursor sair do FILTRO nao pode quebrar a paginacao.

        A subconsulta le por id, sem aplicar os filtros da fila — entao o
        item que serviu de cursor pode ser anotado ou marcado `excluida`
        entre um lote e o proximo sem levar a fila junto. Isso e vantagem do
        desenho por id: com OFFSET, cada saida dessas movia a janela.
        """
        repo = FrameRepository(pg_pool)
        ids = _inserir(pg_raw, tenant, 20)
        p1 = _fila(repo, tenant, page_size=10)["frames"]
        cursor = str(p1[-1]["id"])

        with pg_raw.cursor() as cur:
            cur.execute(
                "UPDATE public.training_frames SET curation_status = 'excluida' "
                "WHERE id = %s",
                (cursor,),
            )

        p2 = _fila(repo, tenant, cursor=cursor, page_size=10)["frames"]
        assert len(p2) == 10
        assert {str(f["id"]) for f in p1} & {str(f["id"]) for f in p2} == set()
        assert len({str(f["id"]) for f in p1} | {str(f["id"]) for f in p2}) == 20
        assert set(ids) == {str(f["id"]) for f in p1} | {str(f["id"]) for f in p2}
