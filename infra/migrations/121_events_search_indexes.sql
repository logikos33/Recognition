-- 052_events_search_indexes.sql
-- Índices de performance para busca investigativa de eventos (task-049).
-- Apenas CREATE INDEX IF NOT EXISTS — idempotente, sem DROP.

-- Índice composto: tenant + module + timestamp (filtros mais frequentes da busca)
CREATE INDEX IF NOT EXISTS idx_alerts_tenant_module_ts
    ON alerts (tenant_id, module_code, created_at DESC);

-- Índice para filtro por câmera dentro do tenant
CREATE INDEX IF NOT EXISTS idx_alerts_tenant_camera_ts
    ON alerts (tenant_id, camera_id, created_at DESC);

-- Índice para filtro por confiança mínima
CREATE INDEX IF NOT EXISTS idx_alerts_confidence
    ON alerts (tenant_id, confidence);
