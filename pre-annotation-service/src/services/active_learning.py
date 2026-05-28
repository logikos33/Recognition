"""Active Learning: priorização de frames por incerteza do modelo."""
import logging

import psycopg2
import psycopg2.extras

from src.config import config

logger = logging.getLogger(__name__)


def _get_conn():
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def calculate_uncertainty(pre_annotations: list) -> float:
    """
    Score de incerteza [0, 1] baseado nas pré-anotações.
    Maior incerteza = mais valor para treino.

    - Sem detecções: incerteza máxima (1.0)
    - Poucas detecções: incerteza alta
    - Confidências baixas: incerteza alta
    """
    if not pre_annotations:
        return 1.0

    confidences = [a.get("confidence", 0.0) for a in pre_annotations]
    avg_confidence = sum(confidences) / len(confidences)

    # Normaliza contagem: até 3 detecções
    detection_factor = min(1.0, len(confidences) / 3.0)

    # Incerteza = combinação de baixa confiança + poucas detecções
    uncertainty = (1.0 - avg_confidence) * 0.7 + (1.0 - detection_factor) * 0.3
    return round(uncertainty, 4)


def prioritize_frames(tenant_id: str, module_code: str) -> dict:
    """
    Ordena frames pré-anotados por incerteza (maior primeiro).
    Atualiza priority_rank e uncertainty_score no banco.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, pre_annotations
            FROM training_frames
            WHERE tenant_id = %s AND module_code = %s AND status = 'pre_annotated'
            ORDER BY created_at
            """,
            (tenant_id, module_code),
        )
        frames = cur.fetchall()

        if not frames:
            return {"prioritized": 0}

        scored = [
            (str(f["id"]), calculate_uncertainty(f["pre_annotations"] or []))
            for f in frames
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        for rank, (frame_id, uncertainty) in enumerate(scored):
            cur.execute(
                "UPDATE training_frames SET priority_rank = %s, uncertainty_score = %s WHERE id = %s",
                (rank, uncertainty, frame_id),
            )

        conn.commit()
        logger.info("prioritized: tenant=%s module=%s count=%d", tenant_id, module_code, len(scored))

        return {
            "prioritized": len(scored),
            "top_5": [
                {"frame_id": fid, "uncertainty": unc}
                for fid, unc in scored[:5]
            ],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
