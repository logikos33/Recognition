#!/usr/bin/env python3
"""
add_epi_classes_rvb.py — Cria a classe custom 'Sem botas' (ausência) do
tenant RVB em yolo_classes.

NUNCA roda automaticamente. NUNCA importado por railway_start.py nem por
run_migrations — é um script de dados (achado feedback_seed_not_migration.md:
dado de cliente/taxonomia por tenant é script env-gated manual, nunca
migration numerada).

A taxonomia EPI da RVB (yolo_classes, tenant custom) já tem: Protetor
auditivo, Sem protetor de ouvido, mascara, Uso incorreto de mascara, Sem
mascara, Botas. Falta APENAS 'Sem botas' — a classe de ausência que fecha o
par com 'Botas'. Este script cria só essa linha, com display_order logo após
a última classe existente do tenant/módulo (não hardcoded).

Idempotente: se 'Sem botas' já existir (não arquivada) para o tenant/módulo,
não faz nada.

Uso:
    DATABASE_URL=postgresql://... CONFIRM_OPS=1 python3 scripts/ops/add_epi_classes_rvb.py

Variáveis de ambiente:
    DATABASE_URL     PostgreSQL connection string (obrigatório)
    CONFIRM_OPS      precisa ser exatamente "1" — hard gate
    RVB_MODULE_CODE  módulo das classes (default: epi — módulo âncora da RVB)
    FORMALIZE_OCULOS somente lido dentro de _optional_formalize_oculos_custom,
                     que NÃO é chamada pelo fluxo principal (ver docstring da
                     função) — presente no arquivo, não no caminho de execução.

Saída: só contagens (nenhum dado de anotação/frame é impresso).
"""
import os
import sys

# ── Hard gate ────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("[add_epi_classes_rvb] ERRO: DATABASE_URL não definida.")
    sys.exit(1)

if os.environ.get("CONFIRM_OPS") != "1":
    print("[add_epi_classes_rvb] BLOQUEADO — CONFIRM_OPS != '1'.")
    print("[add_epi_classes_rvb]   Rode com: CONFIRM_OPS=1 DATABASE_URL=... python3 scripts/ops/add_epi_classes_rvb.py")
    sys.exit(1)

try:
    import psycopg2
except ImportError as exc:
    print(f"[add_epi_classes_rvb] ERRO: dependência faltando: {exc}")
    print("  Instale: pip install psycopg2-binary")
    sys.exit(1)

RVB_TENANT_SLUG = "rvb"
MODULE_CODE = os.environ.get("RVB_MODULE_CODE", "epi")

NEW_CLASS_NAME = "Sem botas"
NEW_CLASS_COLOR = "#b45309"  # âmbar-700 — distinto das demais cores custom da RVB

# Namespacing entre module_classes (catálogo) e yolo_classes (custom do
# tenant) — mesma constante de app/domain/services/class_namespace.py.
# Duplicado aqui (não importado) de propósito: este script roda fora do
# contexto da app Flask (sem PYTHONPATH garantido para app.*) — o valor é
# uma constante estável documentada, não lógica de negócio duplicada.
TENANT_CLASS_ID_OFFSET = 100_000


def _namespace(yolo_class_id: int) -> int:
    return TENANT_CLASS_ID_OFFSET + int(yolo_class_id)


def _optional_formalize_oculos_custom(cur, tenant_id: str) -> None:
    """[NÃO CHAMADA NO FLUXO PRINCIPAL — default OFF, pendente decisão D-103]

    óculos/Sem óculos JÁ EXISTEM como classes GLOBAIS do catálogo
    (module_classes: glasses=class_id 6, no_glasses=class_id 7, módulo epi)
    e JÁ ESTÃO anotadas na RVB (79 + 26 frame_annotations apontando pros ids
    globais 6/7). D-103: taxonomia global de demo != taxonomia custom da RVB
    — reusar o catálogo global é válido e é a situação atual; "formalizar"
    como classes custom do tenant é uma migração de dado, não uma correção.

    SE algum dia Vitor decidir migrar (guardado atrás de
    FORMALIZE_OCULOS=="1", e mesmo assim só roda se este helper for chamado
    explicitamente por quem opera o script — main() nunca chama):
      1. INSERT em yolo_classes (tenant_id, module_code) duas linhas: 'óculos'
         e 'Sem óculos' (mesmo padrão de add_class deste arquivo).
      2. Reaponta frame_annotations do tenant RVB de class_id=6/7 (globais)
         para os novos ids namespaced (100000+id), igual ao passo (a) de
         unify_classes_rvb.py (UPDATE ... FROM training_frames WHERE
         fa.frame_id = tf.id AND tf.tenant_id = %s AND fa.class_id = ANY(%s)).
      3. NENHUMA anotação é apagada — só reapontada.

    Esta função é só o esqueleto do plano acima, documentado para quando a
    decisão vier — não implementa o passo 2 porque não deve rodar agora.
    """
    if os.environ.get("FORMALIZE_OCULOS") != "1":
        print("[add_epi_classes_rvb] _optional_formalize_oculos_custom: "
              "FORMALIZE_OCULOS != '1' — no-op.")
        return
    raise NotImplementedError(
        "óculos/Sem óculos custom da RVB: pendente decisão D-103 "
        "(reusar catálogo global vs. migrar para custom). Não implementado "
        "de propósito — ver docstring desta função."
    )


def main() -> None:
    print("[add_epi_classes_rvb] Conectando ao banco...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute("SELECT id FROM tenants WHERE slug = %s", (RVB_TENANT_SLUG,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Tenant slug={RVB_TENANT_SLUG!r} não encontrado.")
        tenant_id = str(row[0])
        print(f"[add_epi_classes_rvb] Tenant RVB: {tenant_id}")

        # ── Idempotência: já existe (não arquivada)? ──────────────────────
        cur.execute(
            "SELECT id FROM yolo_classes "
            "WHERE tenant_id = %s AND module_code = %s AND name = %s "
            "AND archived_at IS NULL",
            (tenant_id, MODULE_CODE, NEW_CLASS_NAME),
        )
        existing = cur.fetchone()
        if existing:
            print(
                f"[add_epi_classes_rvb] '{NEW_CLASS_NAME}' já existe "
                f"(yolo_classes.id={existing[0]}, class_id namespaced="
                f"{_namespace(existing[0])}) — nada a fazer."
            )
            conn.rollback()
            return

        # ── user_id: reaproveita o mesmo ator já usado nas outras classes
        # custom deste tenant/módulo (coluna NOT NULL, sem significado de
        # tenant — o isolamento real é tenant_id, migration 093) ──────────
        cur.execute(
            "SELECT user_id FROM yolo_classes "
            "WHERE tenant_id = %s AND module_code = %s "
            "ORDER BY id LIMIT 1",
            (tenant_id, MODULE_CODE),
        )
        user_row = cur.fetchone()
        if not user_row:
            raise RuntimeError(
                f"Nenhuma classe custom existente para tenant={tenant_id}, "
                f"module={MODULE_CODE!r} — não há user_id de referência para "
                "reaproveitar. Rode com um user_id explícito (fora do "
                "escopo deste script)."
            )
        user_id = user_row[0]

        # ── display_order: logo após a última classe do tenant/módulo ────
        cur.execute(
            "SELECT COALESCE(MAX(display_order), 0) FROM yolo_classes "
            "WHERE tenant_id = %s AND module_code = %s",
            (tenant_id, MODULE_CODE),
        )
        display_order = cur.fetchone()[0] + 1

        cur.execute(
            "INSERT INTO yolo_classes (user_id, name, color, tenant_id, module_code, display_order) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, NEW_CLASS_NAME, NEW_CLASS_COLOR, tenant_id, MODULE_CODE, display_order),
        )
        new_id = cur.fetchone()[0]
        print(
            f"[add_epi_classes_rvb] '{NEW_CLASS_NAME}' criada: "
            f"yolo_classes.id={new_id}, display_order={display_order}, "
            f"class_id namespaced={_namespace(new_id)}"
        )
        print("[add_epi_classes_rvb] linhas inseridas: 1")

        conn.commit()
        print("[add_epi_classes_rvb] OK — transação commitada.")

    except Exception as exc:
        conn.rollback()
        print(f"[add_epi_classes_rvb] ERRO — rollback executado: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
