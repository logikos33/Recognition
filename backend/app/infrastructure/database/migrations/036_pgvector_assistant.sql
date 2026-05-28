-- Migration 036: pgvector para RAG do EPI Assistant
-- Requer: postgresql-16-pgvector ou pgvector instalado localmente
-- Instalar: brew install pgvector   (macOS)

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS assistant_docs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content     TEXT NOT NULL,
    embedding   vector(768),
    source      VARCHAR(200),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assistant_docs_embedding
    ON assistant_docs USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_assistant_docs_source
    ON assistant_docs (source);
