"""A polaridade de classe nova não pode virar "conformidade" sozinha.

`railway_start.py` re-roda TODA migration a cada boot. A versão original da 125
terminava com um `UPDATE ... SET is_violation = FALSE WHERE is_violation IS
NULL` SEM recorte, e nenhuma rota da API grava `is_violation` — logo toda
classe criada pelo anotador nascia NULL e virava FALSE no reinício seguinte.

Efeito medido: uma classe de violação cujo nome não comece por "Sem " ou "Uso
incorreto" ("Fumando", "Área restrita", "Uso indevido de escada") passava a
contar como CONFORMIDADE, sumia da tela de violações e inflava a taxa de
conformidade mostrada ao cliente. Sem correção possível pela UI.

Contradizia o cabeçalho da própria migration ("NULL = ninguém decidiu ainda";
"o prefixo é usado UMA VEZ, não é regra de runtime") e a ADR-0063 §2.
"""
import re
from pathlib import Path

# tests/unit/infrastructure/ -> unit -> tests -> api -> services -> raiz
MIGRATION = (
    Path(__file__).resolve().parents[5]
    / "infra" / "migrations" / "125_yolo_classes_is_violation.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _sem_comentarios(texto: str) -> str:
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("--")
    )


def test_a_migration_existe():
    assert MIGRATION.is_file(), f"não achei {MIGRATION}"


def test_nao_ha_backfill_de_presenca_sem_recorte():
    """O caso exato que erodia: NULL -> FALSE em tudo, a cada boot."""
    corpo = _sem_comentarios(_sql())
    updates = re.findall(
        r"UPDATE\s+public\.yolo_classes.*?;", corpo, re.S | re.I,
    )
    presenca = [u for u in updates if re.search(r"is_violation\s*=\s*FALSE", u, re.I)]
    assert presenca, "o backfill de presença sumiu — base nova ficaria sem conformidade"
    for u in presenca:
        assert "created_at" in u, (
            "backfill de presença SEM recorte por created_at: a cada boot ele "
            "converte 'ninguém decidiu' em 'é conformidade' para toda classe nova"
        )


def test_o_backfill_de_violacao_continua_so_para_quem_nunca_decidiu():
    corpo = _sem_comentarios(_sql())
    violacao = [
        u for u in re.findall(r"UPDATE\s+public\.yolo_classes.*?;", corpo, re.S | re.I)
        if re.search(r"is_violation\s*=\s*TRUE", u, re.I)
    ]
    assert violacao, "sumiu o valor inicial das classes de ausência"
    for u in violacao:
        assert re.search(r"is_violation\s+IS\s+NULL", u, re.I), (
            "sem `WHERE is_violation IS NULL` o backfill desfaz correção humana"
        )


def test_a_coluna_continua_anulavel():
    """NULL é o estado 'ninguém decidiu' que a leitura trata como violação."""
    corpo = _sem_comentarios(_sql()).upper()
    assert "ADD COLUMN IF NOT EXISTS IS_VIOLATION BOOLEAN" in corpo.replace("  ", " ")
    assert "IS_VIOLATION BOOLEAN NOT NULL" not in corpo
    assert "IS_VIOLATION BOOLEAN DEFAULT" not in corpo
