"""
CORE auto_version.py — Auto-versionamento por deploy Railway.

Cria uma entrada em system_versions automaticamente a cada novo deploy,
usando as env vars que o Railway injeta:
  RAILWAY_GIT_COMMIT_SHA     — SHA do commit deployado
  RAILWAY_GIT_COMMIT_MESSAGE — Mensagem do commit

Derivação de version_type a partir do prefixo Conventional Commit:
  feat! / BREAKING CHANGE → major
  feat                    → minor
  fix, refactor, chore…   → patch (default)

Idempotente: o UNIQUE INDEX em system_versions(git_sha) garante
que múltiplos workers gunicorn não criam entradas duplicadas.
INSERT ... ON CONFLICT DO NOTHING é seguro para concorrência.

Em desenvolvimento local (sem env vars Railway) a função retorna
imediatamente sem efeito colateral.
"""
import json
import logging
import os
import re
import uuid

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Função pública — chamada por create_app() após pool init
# ---------------------------------------------------------------------------

def auto_create_version_on_deploy() -> None:
    """
    Detecta novo deploy Railway e registra versão automaticamente.

    Nunca levanta exceção — falhas são logadas silenciosamente para
    não impedir o startup da aplicação.
    """
    sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:40].strip()
    msg = os.environ.get("RAILWAY_GIT_COMMIT_MESSAGE", "").strip()

    if not sha:
        return  # dev local — sem env vars Railway

    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return

        with pool.get_connection() as conn, conn.cursor() as cur:
            # Idempotente: verifica se SHA já foi registrado
            cur.execute(
                "SELECT id FROM public.system_versions WHERE git_sha = %s",
                (sha,),
            )
            if cur.fetchone():
                logger.debug("auto_version: sha=%s já registrado, pulando", sha[:8])
                return

            version_type = _infer_version_type(msg)
            new_version = _next_version(cur, version_type)
            title = (msg.split("\n")[0] or f"Deploy {sha[:8]}")[:200]
            snapshot = build_snapshot(cur)
            new_id = str(uuid.uuid4())

            # Desmarca versão atual
            cur.execute(
                "UPDATE public.system_versions SET is_current = false WHERE is_current = true"
            )

            # Insere nova versão — ON CONFLICT garante idempotência multi-worker
            cur.execute(
                """
                INSERT INTO public.system_versions
                  (id, version, version_type, title, is_current, config_snapshot, git_sha)
                VALUES (%s, %s, %s, %s, true, %s, %s)
                ON CONFLICT (git_sha) WHERE git_sha IS NOT NULL DO NOTHING
                """,
                (new_id, new_version, version_type, title, json.dumps(snapshot), sha),
            )

            if cur.rowcount == 0:
                # Outro worker ganhou a corrida — desfaz o UPDATE anterior
                cur.execute(
                    "UPDATE public.system_versions SET is_current = true "
                    "WHERE id = ("
                    "SELECT id FROM public.system_versions ORDER BY created_at DESC LIMIT 1)"
                )
                conn.commit()
                return

            # Changelog automático
            importance = (
                "critical" if version_type == "major"
                else "high" if version_type == "minor" else "normal"
            )
            cur.execute(
                """
                INSERT INTO public.system_changelog
                  (version_id, category, importance, title, affected_area)
                VALUES (%s, 'infra', %s, %s, 'system')
                """,
                (new_id, importance, f"Deploy automático: {title}"),
            )

        conn.commit()
        logger.info(
            "auto_version_created: %s (%s) sha=%s title=%r",
            new_version, version_type, sha[:8], title[:60],
        )

    except Exception as exc:
        logger.warning("auto_version_failed: %s", exc)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _infer_version_type(msg: str) -> str:
    """Deriva major/minor/patch do prefixo Conventional Commit."""
    first_line = msg.split("\n")[0].lower().strip()
    body = msg.lower()

    if "breaking change" in body or re.match(r"^feat!", first_line):
        return "major"
    if re.match(r"^feat[\(:]", first_line):
        return "minor"
    return "patch"


def _next_version(cur, version_type: str) -> str:
    """Incrementa a versão atual ou parte de 0.0.0."""
    cur.execute(
        "SELECT version FROM public.system_versions "
        "WHERE is_current = true ORDER BY created_at DESC LIMIT 1"
    )
    row = cur.fetchone()
    current = row["version"] if row else "0.0.0"

    try:
        major, minor, patch = (int(x) for x in current.split("."))
    except Exception:
        major, minor, patch = 0, 0, 0

    if version_type == "major":
        return f"{major + 1}.0.0"
    if version_type == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def build_snapshot(cur) -> dict:
    """
    Captura estado configurável dos tenants e planos para snapshot.

    Exportado para routes_versions.py evitar duplicação.
    """
    cur.execute("""
        SELECT id, slug, plan, modules_enabled, feature_flags, is_active
        FROM public.tenants
        ORDER BY created_at
    """)
    tenants = [
        {
            "id": str(r["id"]),
            "slug": r["slug"],
            "plan": r["plan"],
            "modules_enabled": r["modules_enabled"] or [],
            "feature_flags": r["feature_flags"] or {},
            "is_active": r["is_active"],
        }
        for r in cur.fetchall()
    ]

    cur.execute("SELECT id, slug, name, modules_allowed FROM public.plans ORDER BY slug")
    plans = [
        {
            "id": str(r["id"]),
            "slug": r["slug"],
            "name": r["name"],
            "modules_allowed": r["modules_allowed"] or [],
        }
        for r in cur.fetchall()
    ]

    return {"tenants": tenants, "plans": plans}
