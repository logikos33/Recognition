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
"o prefixo é usado UMA VEZ, não é regra de runtime") e a ADR-0065 §2.
"""
import re
from pathlib import Path

# tests/unit/infrastructure/ -> unit -> tests -> api -> services -> raiz
_MIGRACOES = Path(__file__).resolve().parents[5] / "infra" / "migrations"
MIGRATION = _MIGRACOES / "125_yolo_classes_is_violation.sql"
CORRECAO = _MIGRACOES / "127_polaridade_nao_erode.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _sem_comentarios(texto: str) -> str:
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("--")
    )


def test_as_duas_migrations_existem():
    assert MIGRATION.is_file(), f"não achei {MIGRATION}"
    assert CORRECAO.is_file(), f"não achei {CORRECAO}"


def test_a_125_nao_pode_ser_editada():
    """Forward-only aqui é MÁQUINA: o ledger aborta o boot por checksum.

    Eu editei a 125 para recortar o backfill e o deploy da API morreu com
    "MIGRATION EDITADA ... checksum divergente ... Abortando o boot". O guard
    estava certo; o conserto virou a 127.
    """
    import hashlib

    aplicado = "f54f52fefcdf1485b11dfdd45625cf8f6867c39fdb438f93fd5fe60da167cdbe"
    atual = hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
    assert atual == aplicado, (
        "125 divergiu do checksum já registrado no ledger — o boot da API vai "
        "abortar. Corrija com uma migration NOVA."
    )


def test_a_127_devolve_o_null_com_recorte():
    """Em modo legado a 127 roda logo após a 125, desfazendo o excesso dela."""
    corpo = _sem_comentarios(CORRECAO.read_text(encoding="utf-8"))
    assert re.search(r"SET\s+is_violation\s*=\s*NULL", corpo, re.I), (
        "a 127 existe para DEVOLVER o NULL que a 125 apaga"
    )
    assert "created_at" in corpo, (
        "sem recorte por created_at a 127 apagaria também a polaridade "
        "inicial legítima das classes antigas"
    )
    assert re.search(r"is_violation\s+IS\s+FALSE", corpo, re.I), (
        "só mexe no que virou FALSE — nunca no que alguém marcou como violação"
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
