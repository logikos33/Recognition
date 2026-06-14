-- Adiciona módulo 'quality' ao JSONB modules_enabled de todos os tenants que não o possuem.
-- modules_enabled é JSONB (definido em 023_tenant_schema_fields.sql), não array PostgreSQL.
-- Idempotente: WHERE NOT (modules_enabled @> '["quality"]') evita duplicata.
UPDATE tenants
SET modules_enabled = modules_enabled || '["quality"]'::jsonb
WHERE NOT (modules_enabled @> '["quality"]'::jsonb);
