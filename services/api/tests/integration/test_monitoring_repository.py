"""
Integração — EdgeMonitoringRepository contra Postgres real (C-04).

Valida o SQL que os unit tests de /api/v1/monitoring só mockam:
  - get_monitoring_command: LIKE 'monitoring.%' esconde comandos de outros
    tipos (ex.: update_camera_config) mesmo com command_id conhecido
  - upsert_thresholds: INSERT ... ON CONFLICT (site_id) DO UPDATE (migration 116)
  - last_detection_per_camera: DISTINCT ON + janela + contagem por câmera

Pulado automaticamente sem INTEGRATION_DATABASE_URL/HARNESS_DATABASE_URL
(mesmo padrão de test_edge_fleet_overview.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.infrastructure.database.repositories.edge_monitoring_repository import (
    EdgeMonitoringRepository,
)


def _insert_site(cur, tenant_id: str, name: str | None = None) -> str:
    sid = str(uuid4())
    cur.execute(
        """
        INSERT INTO public.edge_sites (id, tenant_id, name, deployment_mode, status)
        VALUES (%s, %s, %s, 'edge', 'active')
        """,
        (sid, tenant_id, name or f"site-{sid[:8]}"),
    )
    return sid


def _insert_command(
    cur, tenant_id: str, site_id: str, command_type: str, command_id: str,
    status: str = "done",
) -> None:
    cur.execute(
        """
        INSERT INTO public.edge_commands
            (tenant_id, site_id, command_type, payload, status, command_id, result)
        VALUES (%s, %s, %s, '{}'::jsonb, %s, %s, '{"ok": true}'::jsonb)
        """,
        (tenant_id, site_id, command_type, status, command_id),
    )


def _insert_detection(
    cur, tenant_id: str, site_id: str, camera_id: str | None,
    occurred_at: datetime, received_at: datetime,
) -> None:
    cur.execute(
        """
        INSERT INTO public.edge_events
            (tenant_id, site_id, camera_id, event_type, payload, occurred_at, received_at)
        VALUES (%s, %s, %s, 'detection', '{}'::jsonb, %s, %s)
        """,
        (tenant_id, site_id, camera_id, occurred_at, received_at),
    )


class TestGetMonitoringCommand:
    def test_monitoring_visivel_outro_tipo_invisivel(self, pg_pool, pg_raw, tenant_id):
        """Mesmo padrão de command_id: 'monitoring.query' aparece;
        'update_camera_config' → None (rota responde 404)."""
        repo = EdgeMonitoringRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id)

        _insert_command(cur, tenant_id, sid, "monitoring.query", "mon-q-int-visivel")
        _insert_command(cur, tenant_id, sid, "update_camera_config", "mon-q-int-oculto")

        row = repo.get_monitoring_command("mon-q-int-visivel")
        assert row is not None
        assert row["status"] == "done"
        assert row["result"] == {"ok": True}  # coluna result agora É lida pelo cloud

        assert repo.get_monitoring_command("mon-q-int-oculto") is None
        assert repo.get_monitoring_command("mon-q-inexistente") is None


class TestThresholdsUpsert:
    def test_roundtrip_e_on_conflict(self, pg_pool, pg_raw, tenant_id):
        repo = EdgeMonitoringRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id)

        assert repo.get_thresholds(sid) is None

        row = repo.upsert_thresholds(sid, tenant_id, {"cpu_pct_max": 90}, None)
        assert row is not None
        assert row["thresholds"] == {"cpu_pct_max": 90}

        # Segundo upsert no mesmo site → UPDATE, não erro de PK
        row = repo.upsert_thresholds(
            sid, tenant_id, {"cpu_pct_max": 80, "alertas_ativos": True}, None
        )
        assert row["thresholds"] == {"cpu_pct_max": 80, "alertas_ativos": True}

        stored = repo.get_thresholds(sid)
        assert stored is not None
        assert stored["thresholds"] == {"cpu_pct_max": 80, "alertas_ativos": True}


class TestLastDetectionPerCamera:
    def test_janela_contagem_e_ultimo_evento(self, pg_pool, pg_raw, tenant_id):
        repo = EdgeMonitoringRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id)
        now = datetime.now(timezone.utc)
        cam_a, cam_b = str(uuid4()), str(uuid4())

        # cam_a: 2 eventos na janela (último com lag de 5s) + 1 fora da janela
        _insert_detection(
            cur, tenant_id, sid, cam_a,
            now - timedelta(minutes=30), now - timedelta(minutes=30) + timedelta(seconds=2),
        )
        _insert_detection(
            cur, tenant_id, sid, cam_a,
            now - timedelta(minutes=5), now - timedelta(minutes=5) + timedelta(seconds=5),
        )
        _insert_detection(
            cur, tenant_id, sid, cam_a,
            now - timedelta(hours=3), now - timedelta(hours=3) + timedelta(seconds=1),
        )
        # cam_b: 1 evento na janela
        _insert_detection(
            cur, tenant_id, sid, cam_b,
            now - timedelta(minutes=10), now - timedelta(minutes=10) + timedelta(seconds=3),
        )

        rows = {str(r["camera_id"]): r for r in repo.last_detection_per_camera(sid, 60)}
        assert set(rows) == {cam_a, cam_b}

        a = rows[cam_a]
        assert a["detections_in_window"] == 2  # o evento de 3h atrás fica fora
        # DISTINCT ON pega o MESMO evento (o mais recente) → lag real de 5s
        lag = (a["last_received_at"] - a["last_occurred_at"]).total_seconds()
        assert abs(lag - 5.0) < 0.5
        assert rows[cam_b]["detections_in_window"] == 1
