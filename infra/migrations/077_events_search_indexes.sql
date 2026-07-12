-- 062 — Índices para busca investigativa (task-049)
-- Idempotente: CREATE INDEX IF NOT EXISTS; seguro rodar 2x; sem DROP.
--
-- idx_alerts_tenant_created: acelera filtragem por tenant + ordenação por data
-- idx_alerts_tenant_module_created: cobre consultas com module_code + range de datas
-- idx_alerts_tenant_camera: cobre filtragem por câmera(s) específica(s)

CREATE INDEX IF NOT EXISTS idx_alerts_tenant_created
  ON alerts(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_tenant_module_created
  ON alerts(tenant_id, module_code, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_tenant_camera
  ON alerts(tenant_id, camera_id);
