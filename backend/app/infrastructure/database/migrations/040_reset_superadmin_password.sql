-- 040_reset_superadmin_password.sql
-- Redefine senha do superadmin vitor@logikos.com para logikos123
-- Idempotente — seguro rodar múltiplas vezes.

UPDATE users
SET password_hash = '$2b$12$2X2POe45QcgGVjZjBN39RuUpolTjPnYi/KATQG8O4UxD8v.fIES5.'
WHERE email = 'vitor@logikos.com';
