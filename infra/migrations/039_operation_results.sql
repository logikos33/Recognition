-- 039_operation_results.sql
-- Histórico de resultados por operação (últimos N por operation_id)

CREATE TABLE IF NOT EXISTS operation_results (
    id           BIGSERIAL PRIMARY KEY,
    operation_id INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    result_json  JSONB NOT NULL,
    evaluated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_operation
    ON operation_results(operation_id, evaluated_at DESC);

CREATE INDEX IF NOT EXISTS idx_results_evaluated_at
    ON operation_results(evaluated_at DESC);
