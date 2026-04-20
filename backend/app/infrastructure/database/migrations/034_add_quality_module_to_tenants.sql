-- Adiciona módulo 'quality' ao array modules_enabled de todos os tenants que não o possuem.
-- Idempotente: WHERE NOT ('quality' = ANY(modules_enabled)) evita duplicata.
UPDATE tenants
SET modules_enabled = array_append(modules_enabled, 'quality')
WHERE NOT ('quality' = ANY(modules_enabled));
