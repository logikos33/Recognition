"""
Integration: `total_situacoes` (CTE de rajada, `AlertRepository.list_with_filters`)
com Postgres REAL — o `LAG`/`PARTITION BY`/`COUNT FILTER` da query não roda
em nenhum teste com mock (`tests/unit/infrastructure/test_alert_repository.py`
só verifica que a query EXISTE e recebe os params certos, nunca o resultado
real do SQL contra dados).

Fixture = o achado que abriu a rodada ux2/dedup (ver `rajada.py`): MESMA
câmera, 33 alertas "Sem mascara" + 33 "Sem Luvas" intercalados dentro de
~2 minutos (gap de 1-2s entre eventos consecutivos, nunca > `DEDUP_WINDOW_SECONDS`).
66 linhas, 2 situações reais.

Mata (sem banco real, os dois sobrevivem):
  - `PARTITION BY camera_id, classe` → só `camera_id`: como os eventos estão
    INTERCALADOS por classe mas próximos no tempo, remover `classe` da
    partição funde as duas rajadas numa só sessão contínua (gap nunca > 60s
    ao longo dos 66 eventos) — `total_situacoes` cairia para 1.
  - `WHERE anterior IS NULL OR gap > janela` → só `gap > janela`: o primeiro
    evento de cada partição tem `LAG` NULL; `NULL > 60` é NULL, e `FILTER`
    descarta NULL como falso — as duas sessões (nenhuma tem gap > 60s no
    meio) deixariam de contar, `total_situacoes` cairia para 0.

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.infrastructure.database.repositories.alert_repository import AlertRepository

BASE = datetime(2026, 8, 25, 13, 39, 0, tzinfo=timezone.utc)
MASCARA = "Sem mascara"
LUVAS = "Sem Luvas"


def _insert_user(cur, tenant_id: str) -> str:
    uid = str(uuid4())
    cur.execute(
        "INSERT INTO public.users (id, email, password_hash, name, role, tenant_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (uid, f"rajada-{uid[:8]}@test.dev", "x", "IntTest Rajada", "operator", tenant_id),
    )
    return uid


def _insert_camera(cur, tenant_id: str, user_id: str) -> str:
    cid = str(uuid4())
    cur.execute(
        "INSERT INTO public.cameras (id, tenant_id, user_id, name, location, host, port) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (cid, tenant_id, user_id, "Canal 8", "Expedição", "192.168.1.1", 554),
    )
    return cid


def _insert_alert(cur, tenant_id: str, camera_id: str, classe: str, created_at: datetime) -> None:
    cur.execute(
        "INSERT INTO public.alerts "
        "  (id, camera_id, tenant_id, module_code, violations, confidence, "
        "   evidence_key, created_at) "
        "VALUES (%s, %s, %s, 'epi', %s::jsonb, %s, %s, %s)",
        (
            str(uuid4()), camera_id, tenant_id,
            json.dumps([{"class": classe, "confidence": 0.9}]),
            0.9, f"evidence/{uuid4()}.jpg", created_at,
        ),
    )


def _purge_tenant(pg_raw, tid: str) -> None:
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.alerts WHERE tenant_id = %s", (tid,))
        cur.execute("DELETE FROM public.cameras WHERE tenant_id = %s", (tid,))
        cur.execute("DELETE FROM public.users WHERE tenant_id = %s", (tid,))


def test_66_linhas_intercaladas_sao_2_situacoes(pg_raw, pg_pool, tenant_id):
    """33 "Sem mascara" + 33 "Sem Luvas", mesma câmera, intercalados a cada
    3s (~99s de span, sempre < 2min) — a rajada real que motivou o recurso."""
    with pg_raw.cursor() as cur:
        user_id = _insert_user(cur, tenant_id)
        cam = _insert_camera(cur, tenant_id, user_id)
        for i in range(33):
            t = BASE + timedelta(seconds=3 * i)
            _insert_alert(cur, tenant_id, cam, MASCARA, t)
            _insert_alert(cur, tenant_id, cam, LUVAS, t + timedelta(seconds=1))
    try:
        result = AlertRepository(pg_pool).list_with_filters(
            tenant_id=tenant_id, limit=100, offset=0
        )
        assert result["total"] == 66
        assert result["total_situacoes"] == 2
    finally:
        _purge_tenant(pg_raw, tenant_id)
