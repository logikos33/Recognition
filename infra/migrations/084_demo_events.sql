-- Migration 084: Tabela apartada demo_events (eventos mock de demonstração)
-- Eventos fictícios semeados pelo superadmin via /api/v1/admin/demo-events para
-- demonstrar a Investigação de Eventos em tenants sem dados reais.
-- APARTADA de alerts de propósito: remoção de demo NUNCA toca alertas reais.
--
-- created_at  = timestamp DO EVENTO (espalhado pelos últimos 7 dias pelo seeder)
-- seeded_at   = auditoria de quando o lote foi criado
-- batch_id    = agrupa eventos de um mesmo seed (remoção/auditoria)
-- camera_label= nome exibido mesmo em tenants novos sem câmeras (evita JOIN obrigatório)
--
-- Forward-only e idempotente: pode ser executada múltiplas vezes sem erro.
-- SEM seed de dados aqui (regra "seed não é migration") — dados entram só pelo endpoint admin.

CREATE TABLE IF NOT EXISTS demo_events (
    id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    camera_id    UUID          REFERENCES cameras(id) ON DELETE SET NULL,
    camera_label VARCHAR(255)  NOT NULL DEFAULT 'Câmera Demo',
    module_code  VARCHAR(50)   NOT NULL DEFAULT 'epi',
    violations   JSONB         NOT NULL DEFAULT '[]',
    confidence   FLOAT         NOT NULL DEFAULT 0.0,
    evidence_key VARCHAR(500),
    acknowledged BOOLEAN       NOT NULL DEFAULT FALSE,
    batch_id     UUID          NOT NULL,
    created_by   UUID          REFERENCES users(id),
    created_at   TIMESTAMP     NOT NULL DEFAULT NOW(),
    seeded_at    TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demo_events_tenant_created
    ON demo_events (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_demo_events_tenant_module
    ON demo_events (tenant_id, module_code);
