#!/usr/bin/env python3
"""
unify_classes_rvb.py — Curadoria única de classes do tenant RVB (migration 110).

NUNCA roda automaticamente. NUNCA importado por railway_start.py nem por
run_migrations — é um script de dados (achado feedback_seed_not_migration.md:
dado de cliente é script env-gated manual, nunca migration numerada).

Corrige a duplicidade "Protetor auricular" vs "Protetor auditivo" nas classes
custom (yolo_classes) do tenant RVB e define a ordem de exibição no anotador:

    (a) Reaponta frame_annotations do tenant RVB de class_name='Protetor
        auricular' para 'Protetor auditivo' (class_id e class_name) — as
        caixas já anotadas passam a apontar para a classe canônica; NENHUMA
        anotação é apagada (⛔ nunca apagar caixas).
    (b) Arquiva (archived_at = NOW()) as classes obsoletas 'Protetor
        auricular' e 'incluir blur' — saem do anotador sem apagar histórico.
    (c) Define display_order: 1=Protetor auditivo, 2=Sem protetor de ouvido,
        3=mascara, 4=Sem mascara.

Tudo em UMA transação (BEGIN..COMMIT) — ou tudo aplica, ou nada.
Idempotente: rodar 2x não duplica nem falha (passo 1 já não encontra mais
'Protetor auricular' referenciado; passos 2/3 são upserts de estado, não
inserts).

Uso:
    DATABASE_URL=postgresql://... CONFIRM_OPS=1 python3 scripts/ops/unify_classes_rvb.py

Variáveis de ambiente:
    DATABASE_URL   PostgreSQL connection string (obrigatório)
    CONFIRM_OPS    precisa ser exatamente "1" — hard gate
    RVB_MODULE_CODE  módulo das classes (default: epi — módulo âncora da RVB)

Saída: só contagens (nenhum dado de anotação/frame é impresso).

⛔ NÃO EXECUTAR nesta branch — o orquestrador roda este script manualmente
após o deploy (ver prompt de execução do mutirão de curadoria).
"""
import os
import sys

# ── Hard gate ────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("[unify_classes_rvb] ERRO: DATABASE_URL não definida.")
    sys.exit(1)

if os.environ.get("CONFIRM_OPS") != "1":
    print("[unify_classes_rvb] BLOQUEADO — CONFIRM_OPS != '1'.")
    print("[unify_classes_rvb]   Rode com: CONFIRM_OPS=1 DATABASE_URL=... python3 scripts/ops/unify_classes_rvb.py")
    sys.exit(1)

try:
    import psycopg2
except ImportError as exc:
    print(f"[unify_classes_rvb] ERRO: dependência faltando: {exc}")
    print("  Instale: pip install psycopg2-binary")
    sys.exit(1)

RVB_TENANT_SLUG = "rvb"
MODULE_CODE = os.environ.get("RVB_MODULE_CODE", "epi")

OLD_NAME = "Protetor auricular"
NEW_NAME = "Protetor auditivo"
ARCHIVE_NAMES = ("Protetor auricular", "incluir blur")
DISPLAY_ORDER = {
    "Protetor auditivo": 1,
    "Sem protetor de ouvido": 2,
    "mascara": 3,
    "Sem mascara": 4,
}

# Namespacing entre module_classes (catálogo) e yolo_classes (custom do
# tenant) — mesma constante de app/domain/services/class_namespace.py.
# Duplicado aqui (não importado) de propósito: este script roda fora do
# contexto da app Flask (sem PYTHONPATH garantido para app.*) — o valor é
# uma constante estável documentada, não lógica de negócio duplicada.
TENANT_CLASS_ID_OFFSET = 100_000


def _namespace(yolo_class_id: int) -> int:
    return TENANT_CLASS_ID_OFFSET + int(yolo_class_id)


def main() -> None:
    print("[unify_classes_rvb] Conectando ao banco...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute("SELECT id FROM tenants WHERE slug = %s", (RVB_TENANT_SLUG,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Tenant slug={RVB_TENANT_SLUG!r} não encontrado.")
        tenant_id = str(row[0])
        print(f"[unify_classes_rvb] Tenant RVB: {tenant_id}")

        # ── Resolve classes custom do tenant (yolo_classes) por nome ──────
        needed_names = {OLD_NAME, NEW_NAME, *ARCHIVE_NAMES, *DISPLAY_ORDER}
        cur.execute(
            "SELECT id, name FROM yolo_classes "
            "WHERE tenant_id = %s AND module_code = %s AND name = ANY(%s)",
            (tenant_id, MODULE_CODE, list(needed_names)),
        )
        by_name = {name: class_id for class_id, name in cur.fetchall()}

        missing = sorted(needed_names - by_name.keys())
        if missing:
            raise RuntimeError(
                f"Classe(s) não encontrada(s) em yolo_classes (tenant={tenant_id}, "
                f"module={MODULE_CODE!r}): {missing}. Nada foi alterado."
            )

        # ── (a) Reaponta frame_annotations 'Protetor auricular' → 'Protetor auditivo' ──
        new_class_id = _namespace(by_name[NEW_NAME])
        cur.execute(
            "UPDATE frame_annotations fa "
            "SET class_id = %s, class_name = %s "
            "FROM training_frames tf "
            "WHERE fa.frame_id = tf.id AND tf.tenant_id = %s "
            "AND fa.class_name = %s",
            (new_class_id, NEW_NAME, tenant_id, OLD_NAME),
        )
        reassigned = cur.rowcount
        print(f"[unify_classes_rvb] annotations reapontadas: {reassigned}")

        # ── (b) Arquiva classes obsoletas ─────────────────────────────────
        archive_ids = [by_name[name] for name in ARCHIVE_NAMES]
        cur.execute(
            "UPDATE yolo_classes SET archived_at = NOW() "
            "WHERE tenant_id = %s AND module_code = %s "
            "AND id = ANY(%s) AND archived_at IS NULL",
            (tenant_id, MODULE_CODE, archive_ids),
        )
        archived = cur.rowcount
        print(f"[unify_classes_rvb] classes arquivadas: {archived}")

        # ── (c) display_order ─────────────────────────────────────────────
        order_updated = 0
        for name, order in DISPLAY_ORDER.items():
            cur.execute(
                "UPDATE yolo_classes SET display_order = %s "
                "WHERE tenant_id = %s AND module_code = %s AND id = %s "
                "AND display_order IS DISTINCT FROM %s",
                (order, tenant_id, MODULE_CODE, by_name[name], order),
            )
            order_updated += cur.rowcount
        print(f"[unify_classes_rvb] display_order atualizado: {order_updated}")

        conn.commit()
        print("[unify_classes_rvb] OK — transação commitada.")

    except Exception as exc:
        conn.rollback()
        print(f"[unify_classes_rvb] ERRO — rollback executado: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
