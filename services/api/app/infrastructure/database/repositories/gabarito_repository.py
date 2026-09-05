"""Repository: vereditos do gabarito (public.holdout_verdicts, migration 135).

O que esta tabela responde: "nesta imagem, a ausência da classe X era real?",
em três estados — sim / nao / nao_sei. É a régua que `ab_ausencia.py` consome
para comparar as três variantes de detector, e a comparação acontece no nível
da DECISÃO por imagem, não por caixa.

⛔ POR QUE UM REPOSITORY SEPARADO, E NÃO UM MÉTODO EM AnnotationRepository
Porque veredito NÃO É ANOTAÇÃO, e a separação tem de ser estrutural, não
cultural. `AnnotationRepository` fala com `frame_annotations` — a tabela de
onde `versioning_v2._fetch_annotations` e `auto_training` montam o dataset de
treino. Um veredito que morasse lá dependeria de todo leitor lembrar de
filtrá-lo. Morando aqui, ele é INCAPAZ de entrar num export: nenhuma query de
treino conhece esta tabela. Ver o cabeçalho da migration 135.

A regra da casa (uma tabela por repository) e a regra do gabarito apontam para
o mesmo arquivo.
"""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class GabaritoRepository(BaseRepository):
    """Queries SQL para public.holdout_verdicts."""

    def list_fila(self, tenant_id: str, module_code: str) -> list[dict[str, Any]]:
        """A fila do gabarito: os quadros retidos como holdout, na ordem.

        ORDEM — `priority_rank ASC NULLS LAST, captured_at DESC`.
        `priority_rank` carrega a ordem da fila já decidida
        (`docs/quality/evidence/gabarito-v2/fila-gabarito-150.csv`: por
        probabilidade de conter ausência real e pela prioridade de câmera do
        dono), gravada por `scripts/ops/marcar_gabarito.py --ordem`. Coluna
        reaproveitada de propósito: ela já existe, tem índice
        (`idx_frames_priority`), estava 100% NULL e sem NENHUM leitor em
        Python — e "posto na fila por prioridade" é literalmente o que o nome
        diz. Inventar uma coluna nova para o mesmo fato seria migration a mais
        pelo mesmo dado. `NULLS LAST` é o que impede que um quadro promovido a
        holdout depois, sem posto na lista, se enfie na frente da fila do dono.

        Escopo por `tf.tenant_id` (ADR-0017, sem fallback silencioso) e por
        `dataset_role = 'holdout'`: um quadro do pool não é gabarito e não
        aparece aqui nem por engano de query string.

        Uma consulta só para a fila inteira (~150 linhas), com os vereditos já
        agregados por quadro. O celular baixa a fila UMA vez e trabalha em
        cima dela — é isso que faz a tela sobreviver a rede móvel oscilando.
        """
        rows = self._execute(
            "SELECT tf.id, tf.filename, tf.camera_id, tf.captured_at, "
            "       tf.width, tf.height, c.name AS camera_name, "
            "       COALESCE( "
            "         jsonb_object_agg(hv.class_id::text, hv.verdict) "
            "           FILTER (WHERE hv.class_id IS NOT NULL), "
            "         '{}'::jsonb "
            "       ) AS verdicts, "
            "       MAX(hv.reason) AS reason "
            "FROM public.training_frames tf "
            "LEFT JOIN public.cameras c "
            "  ON c.id = tf.camera_id AND c.tenant_id = tf.tenant_id "
            "LEFT JOIN public.holdout_verdicts hv ON hv.frame_id = tf.id "
            "WHERE tf.tenant_id = %s AND tf.module_code = %s "
            "  AND tf.dataset_role = 'holdout' "
            "GROUP BY tf.id, tf.filename, tf.camera_id, tf.captured_at, "
            "         tf.width, tf.height, c.name, tf.priority_rank "
            "ORDER BY tf.priority_rank ASC NULLS LAST, tf.captured_at DESC",
            (str(tenant_id), str(module_code)),
        )
        return [
            {
                "id": str(row["id"]),
                "filename": row["filename"],
                "camera_id": str(row["camera_id"]) if row["camera_id"] else None,
                "camera_name": row["camera_name"],
                "captured_at": (
                    row["captured_at"].isoformat() if row["captured_at"] else None
                ),
                "width": row["width"],
                "height": row["height"],
                "verdicts": row["verdicts"] or {},
                "reason": row["reason"],
            }
            for row in rows
        ]

    def is_holdout_frame(self, frame_id: str, tenant_id: str) -> bool:
        """O quadro existe, é DESTE tenant e é gabarito?

        As três perguntas de uma vez, e a resposta é um booleano — de
        propósito. Distinguir "não existe" de "é de outro tenant" para o
        chamador é exatamente o vazamento de existência que C-01 proíbe: as
        duas viram 404, e nada além disso sai daqui.
        """
        row = self._execute_one(
            "SELECT 1 FROM public.training_frames "
            "WHERE id = %s AND tenant_id = %s AND dataset_role = 'holdout'",
            (str(frame_id), str(tenant_id)),
        )
        return row is not None

    def upsert_verdicts(
        self,
        frame_id: str,
        tenant_id: str,
        verdicts: dict[int, str],
        judged_by: str | None,
        reason: str | None,
    ) -> int:
        """Grava (ou regrava) os vereditos de UM quadro. Devolve quantos.

        IDEMPOTENTE por `ON CONFLICT (frame_id, class_id) DO UPDATE`: reabrir
        a imagem e mudar de ideia SOBRESCREVE. Sem isso, duas respostas
        contraditórias coexistiriam e o A/B leria a que o plano de execução
        sorteasse — um gabarito que muda de valor conforme o ORDER BY não é
        gabarito.

        `judged_at = NOW()` é reescrito a cada gravação, ao contrário de
        `dataset_role_set_at` (que é congelado de propósito). Os dois carimbos
        provam coisas diferentes: aquele prova que o quadro não estava no
        treino anterior — reescrevê-lo apagaria a prova; este responde "quando
        foi dada a resposta que está valendo AGORA", e é a resposta corrente
        que o A/B consome.

        Numa transação só: a tela manda as respostas do quadro em bloco (e o
        atalho "não há pessoa" manda todas as classes de uma vez). Gravar
        metade delas deixaria o quadro num estado que nenhuma tela sabe ler.
        """
        if not verdicts:
            return 0

        def _tx(conn: Any, cur: Any) -> int:
            gravados = 0
            for class_id, verdict in verdicts.items():
                cur.execute(
                    "INSERT INTO public.holdout_verdicts "
                    "  (frame_id, tenant_id, class_id, verdict, reason, "
                    "   judged_by, judged_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, NOW()) "
                    "ON CONFLICT (frame_id, class_id) DO UPDATE SET "
                    "  verdict = EXCLUDED.verdict, "
                    "  reason = EXCLUDED.reason, "
                    "  judged_by = EXCLUDED.judged_by, "
                    "  judged_at = NOW()",
                    (
                        str(frame_id),
                        str(tenant_id),
                        int(class_id),
                        str(verdict),
                        reason,
                        str(judged_by) if judged_by else None,
                    ),
                )
                gravados += 1
            return gravados

        return self._execute_in_transaction(_tx)
