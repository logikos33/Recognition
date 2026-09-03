"""Integração: o veredito do gabarito NÃO chega ao export de treino.

ESTE É O TESTE QUE SUSTENTA A RÉGUA INTEIRA.

Um modelo treinado sobre o próprio exame decora a prova, e toda medição
posterior passa a mentir para cima sem que nada acuse. Todo o resto do
gabarito — a fila, a tela, os três estados — não vale nada se o veredito puder
voltar como caixa de treino. Por isso a prova é contra Postgres REAL: os testes
unitários de `versioning_v2` mockam `annotation_repo._execute` e não exercitam
o SQL de verdade, então um vazamento passaria por eles inteiro.

O que é afirmado aqui, em três camadas independentes:

  1. ESTRUTURA — o veredito vive em `public.holdout_verdicts` (migration 135),
     e o quadro julgado é `dataset_role='holdout'` (migration 133). O export
     lê `frame_annotations` filtrando por `dataset_role='pool'`: nem a tabela
     nem o quadro entram.
  2. QUADRO — `_snapshot_labeled_frames` não devolve o quadro do gabarito.
  3. CAIXA — `_fetch_annotations` não devolve nada com origem no gabarito, e
     o dataset exportado continua exatamente do tamanho que tinha antes de
     alguém julgar qualquer coisa.

A camada 3 é a que fecha a porta de verdade: mesmo que um dia alguém marque o
quadro do gabarito como 'pool' por engano, a asserção de que o CONTEÚDO do
veredito nunca aparece entre as anotações exportadas continua valendo, porque
o veredito não é uma caixa e não mora na tabela de caixas.

MUTAÇÃO (obrigatória, executada e desfeita — ver o relatório da tarefa): fazer
o veredito vazar para o export reprova aqui. Sem essa verificação, um teste
verde só prova que ele roda.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.gabarito_repository import (
    GabaritoRepository,
)
from app.infrastructure.queue.tasks.versioning_v2 import (
    _fetch_annotations,
    _snapshot_labeled_frames,
)

# Classe do catálogo global usada nos dois papéis, de propósito: se o veredito
# vazasse, ele viria com esta MESMA class_id e se misturaria às caixas reais —
# usar uma classe diferente esconderia o vazamento atrás de um filtro.
CLASSE_SEM_LUVAS = 5


@pytest.fixture
def quadro_de_treino(pg_raw, tenant_id: str) -> str:
    """Quadro normal do pool, anotado. É a linha de base do export."""
    frame_id = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.training_frames "
            "(id, frame_number, filename, tenant_id, module_code, is_annotated, "
            " source, curation_status, dataset_role) "
            "VALUES (%s, 1, %s, %s, 'epi', TRUE, 'nvr', 'active', 'pool')",
            (frame_id, "frames/gab/pool.jpg", tenant_id),
        )
        cur.execute(
            "INSERT INTO public.frame_annotations "
            "(frame_id, class_id, x_center, y_center, width, height, class_name) "
            "VALUES (%s, %s, 0.5, 0.5, 0.2, 0.2, 'no_gloves')",
            (frame_id, CLASSE_SEM_LUVAS),
        )
    yield frame_id
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.training_frames WHERE id = %s", (frame_id,))


@pytest.fixture
def quadro_de_gabarito(pg_raw, tenant_id: str) -> str:
    """Quadro retido como gabarito. `is_annotated=TRUE` DE PROPÓSITO.

    É a pior hipótese possível: um quadro que o export levaria se o único
    critério fosse "está anotado". Semeá-lo como não-anotado tornaria o teste
    verde por acidente — ele passaria mesmo com a trava do papel removida.
    """
    frame_id = str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.training_frames "
            "(id, frame_number, filename, tenant_id, module_code, is_annotated, "
            " source, curation_status, dataset_role, dataset_role_set_at) "
            "VALUES (%s, 2, %s, %s, 'epi', TRUE, 'nvr', 'active', 'holdout', NOW())",
            (frame_id, "frames/gab/holdout.jpg", tenant_id),
        )
    yield frame_id
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.training_frames WHERE id = %s", (frame_id,))


@pytest.fixture
def veredito_dado(pg_pool, quadro_de_gabarito: str, tenant_id: str) -> str:
    """O dono julgou: "sim, a ausência de luvas era real nesta imagem"."""
    GabaritoRepository(pg_pool).upsert_verdicts(
        frame_id=quadro_de_gabarito,
        tenant_id=tenant_id,
        verdicts={CLASSE_SEM_LUVAS: "sim"},
        judged_by=None,
        reason=None,
    )
    return quadro_de_gabarito


class TestGabaritoForaDoExport:
    def test_quadro_do_gabarito_nao_entra_no_pool_de_frames(
        self, pg_pool, tenant_id: str, quadro_de_treino: str, veredito_dado: str
    ) -> None:
        rows = _snapshot_labeled_frames(AnnotationRepository(pg_pool), tenant_id, "epi")
        ids = {str(r["id"]) for r in rows}
        assert quadro_de_treino in ids, "o quadro do pool deveria estar no export"
        assert veredito_dado not in ids, (
            "VAZAMENTO: quadro de gabarito entrou no pool de treino — "
            "o modelo treinaria sobre a própria prova"
        )

    def test_veredito_nao_vira_anotacao_exportada(
        self, pg_pool, tenant_id: str, quadro_de_treino: str, veredito_dado: str
    ) -> None:
        rows, _universo = _fetch_annotations(
            AnnotationRepository(pg_pool), tenant_id, "epi"
        )
        frame_ids = {str(r["frame_id"]) for r in rows}
        assert quadro_de_treino in frame_ids
        assert veredito_dado not in frame_ids, (
            "VAZAMENTO: o veredito do gabarito apareceu como anotação de treino"
        )

    def test_julgar_nao_muda_o_tamanho_do_dataset(
        self, pg_pool, pg_raw, tenant_id: str, quadro_de_treino: str,
        quadro_de_gabarito: str,
    ) -> None:
        """A asserção mais forte: julgar não move o export nem em uma linha.

        Mede ANTES e DEPOIS do veredito existir. Contagem igual é a prova de
        que o gabarito não é "filtrado para fora" — ele simplesmente não está
        no caminho.
        """
        repo = AnnotationRepository(pg_pool)
        antes, _ = _fetch_annotations(repo, tenant_id, "epi")
        antes_frames = _snapshot_labeled_frames(repo, tenant_id, "epi")

        GabaritoRepository(pg_pool).upsert_verdicts(
            frame_id=quadro_de_gabarito,
            tenant_id=tenant_id,
            verdicts={CLASSE_SEM_LUVAS: "sim", 7: "nao", 100009: "nao_sei"},
            judged_by=None,
            reason="sem_pessoa",
        )

        depois, _ = _fetch_annotations(repo, tenant_id, "epi")
        depois_frames = _snapshot_labeled_frames(repo, tenant_id, "epi")

        assert len(depois) == len(antes), (
            f"VAZAMENTO: o export ganhou {len(depois) - len(antes)} anotação(ões) "
            "só porque alguém julgou o gabarito"
        )
        assert len(depois_frames) == len(antes_frames)

        # E o veredito EXISTE — senão o teste acima seria verde por não ter
        # gravado nada, que é o pior verde possível.
        with pg_raw.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM public.holdout_verdicts WHERE frame_id = %s",
                (quadro_de_gabarito,),
            )
            assert cur.fetchone()["n"] == 3

    def test_veredito_e_idempotente_e_sobrescreve(
        self, pg_pool, pg_raw, tenant_id: str, quadro_de_gabarito: str
    ) -> None:
        """Reabrir a imagem e mudar de ideia sobrescreve, não duplica.

        Sem isso, duas respostas contraditórias coexistiriam e o A/B leria a
        que o plano de execução sorteasse.
        """
        repo = GabaritoRepository(pg_pool)
        for veredito in ("sim", "nao_sei", "nao"):
            repo.upsert_verdicts(
                frame_id=quadro_de_gabarito,
                tenant_id=tenant_id,
                verdicts={CLASSE_SEM_LUVAS: veredito},
                judged_by=None,
                reason=None,
            )
        with pg_raw.cursor() as cur:
            cur.execute(
                "SELECT verdict FROM public.holdout_verdicts WHERE frame_id = %s",
                (quadro_de_gabarito,),
            )
            linhas = cur.fetchall()
        assert len(linhas) == 1, "três julgamentos viraram três linhas — duplicou"
        assert linhas[0]["verdict"] == "nao", "não ficou valendo o último veredito"

    def test_os_tres_estados_persistem(
        self, pg_pool, pg_raw, tenant_id: str, quadro_de_gabarito: str
    ) -> None:
        """sim / nao / nao_sei sobrevivem ao CHECK do banco.

        O "não sei" é o que impede o gabarito de virar chute; se o CHECK o
        recusasse, a tela quebraria só em produção.
        """
        GabaritoRepository(pg_pool).upsert_verdicts(
            frame_id=quadro_de_gabarito,
            tenant_id=tenant_id,
            verdicts={CLASSE_SEM_LUVAS: "sim", 7: "nao", 100009: "nao_sei"},
            judged_by=None,
            reason=None,
        )
        with pg_raw.cursor() as cur:
            cur.execute(
                "SELECT class_id, verdict FROM public.holdout_verdicts "
                "WHERE frame_id = %s ORDER BY class_id",
                (quadro_de_gabarito,),
            )
            assert {r["class_id"]: r["verdict"] for r in cur.fetchall()} == {
                CLASSE_SEM_LUVAS: "sim",
                7: "nao",
                100009: "nao_sei",
            }


class TestEscopoDeTenant:
    def test_quadro_de_outro_tenant_nao_e_gabarito_deste(
        self, pg_pool, pg_raw, tenant_id: str, quadro_de_gabarito: str
    ) -> None:
        """`is_holdout_frame` é o gate do 404 (C-01).

        O id EXISTE e É holdout — só que de outro tenant. A resposta tem de
        ser a mesma de "não existe": distinguir as duas contaria ao chamador
        que o quadro existe em algum lugar.
        """
        repo = GabaritoRepository(pg_pool)
        assert repo.is_holdout_frame(quadro_de_gabarito, tenant_id) is True
        assert repo.is_holdout_frame(quadro_de_gabarito, str(uuid4())) is False

    def test_a_fila_nao_traz_quadro_de_outro_tenant(
        self, pg_pool, tenant_id: str, quadro_de_gabarito: str
    ) -> None:
        repo = GabaritoRepository(pg_pool)
        assert quadro_de_gabarito in {q["id"] for q in repo.list_fila(tenant_id, "epi")}
        assert repo.list_fila(str(uuid4()), "epi") == []

    def test_a_fila_nao_traz_quadro_do_pool(
        self, pg_pool, tenant_id: str, quadro_de_treino: str, quadro_de_gabarito: str
    ) -> None:
        """Só quadro retido como gabarito entra na fila de triagem."""
        ids = {q["id"] for q in GabaritoRepository(pg_pool).list_fila(tenant_id, "epi")}
        assert quadro_de_gabarito in ids
        assert quadro_de_treino not in ids


class TestOrdemDaFila:
    def test_fila_obedece_priority_rank_e_nao_inventa_ordem(
        self, pg_pool, pg_raw, tenant_id: str
    ) -> None:
        """A ordem é a da `fila-gabarito-150.csv`, gravada em `priority_rank`.

        Quadro promovido a holdout DEPOIS, sem posto na lista do dono, vai
        para o fim (`NULLS LAST`) — nunca se enfia na frente da fila que ele
        decidiu anotar.
        """
        ids = [str(uuid4()) for _ in range(3)]
        with pg_raw.cursor() as cur:
            for frame_id, rank in zip(ids, (7, None, 2)):
                cur.execute(
                    "INSERT INTO public.training_frames "
                    "(id, frame_number, filename, tenant_id, module_code, "
                    " is_annotated, source, curation_status, dataset_role, "
                    " priority_rank, captured_at) "
                    "VALUES (%s, 1, %s, %s, 'epi', FALSE, 'nvr', 'active', "
                    "        'holdout', %s, NOW())",
                    (frame_id, f"frames/gab/{frame_id}.jpg", tenant_id, rank),
                )
        ordem = [q["id"] for q in GabaritoRepository(pg_pool).list_fila(tenant_id, "epi")]
        assert ordem == [ids[2], ids[0], ids[1]]
        with pg_raw.cursor() as cur:
            cur.execute(
                "DELETE FROM public.training_frames WHERE id = ANY(%s::uuid[])", (ids,)
            )
