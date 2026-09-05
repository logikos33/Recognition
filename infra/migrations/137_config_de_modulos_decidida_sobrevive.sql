-- Migration 137 — a configuração de módulos decidida por gente sobrevive ao deploy (#743)
--
-- ═══ O PROBLEMA ═══
--
-- Terceira cara da família que as issues #683 (apaga dado) e #694 (reescreve
-- credencial) abriram: uma migration que REESCREVE CONFIGURAÇÃO a cada boot.
--
-- O loop legado (o que produção roda hoje, sem MIGRATIONS_LEDGER_CUTOVER)
-- reexecuta todo .sql a cada boot. Duas migrations escrevem por cima da coluna
-- `modules_enabled` de `public.tenants` — a mesma coluna que a tela do admin
-- edita (services/api/app/api/v1/admin/routes.py, "UPDATE tenants SET
-- modules_enabled"):
--
--   · 034_add_quality_module_to_tenants.sql devolve o módulo 'quality' a TODO
--     tenant que não o tenha. O admin tira Qualidade pela tela; o próximo
--     deploy devolve, sem log e sem aviso.
--   · 023_tenant_schema_fields.sql é pior: o ON CONFLICT (slug) DO UPDATE não
--     acrescenta, SOBRESCREVE a lista inteira dos tenants 'admin' e 'rvb' pela
--     versionada no git. O RVB é o cliente âncora.
--
-- No DEV, que auto-deploya a cada merge na develop, isso rodava várias vezes
-- por dia: a escolha de módulos não era durável entre deploys.
--
-- ═══ O QUE FOI FEITO, E POR QUE ISTO AQUI É UMA MIGRATION DE SCHEMA ═══
--
-- O conserto de verdade é na guarda de redeploy (infra/migrations/runner_core.py),
-- que passou a reconhecer esta terceira cara: num banco que JÁ TEM TENANT, um
-- arquivo que atribui a `modules_enabled` é PULADO, do mesmo jeito que já era
-- pulado o que faz DROP/DELETE ou atribui a `password_hash`. Em instalação
-- virgem nada muda — é lá que 023/034 foram escritas para rodar.
--
-- Diferente da 034 (só o UPDATE), a 023 carrega DDL junto: as colunas
-- `schema_name`, `plan` e `modules_enabled`, a unique de schema_name e o índice
-- de lookup do middleware. Pular o arquivo INTEIRO num banco que tem tenant mas
-- nunca rodou a 023 deixaria essas colunas de fora — e a guarda pula por
-- arquivo, não por statement (o runner manda o .sql inteiro num execute; partir
-- SQL em statements exigiria um parser, que é remédio pior que a doença).
--
-- Esta migration fecha esse buraco: repete a parte de SCHEMA da 023, toda
-- idempotente (ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS / DO block
-- que confere a constraint antes). Roda depois da 023 na ordem numérica, no
-- MESMO passe, e nunca é pulada — não atribui a nada, só garante estrutura.
--
-- O que NÃO vem junto, de propósito:
--   · os INSERT de tenant ('admin', 'rvb') da 023 — semente de dado de cliente
--     não é migration (decisão registrada do projeto), e num banco estabelecido
--     esses tenants existem;
--   · o UPDATE do tenant default da 023 — backfill `WHERE schema_name IS NULL`,
--     que já rodou quando aquele banco era virgem;
--   · qualquer escrita em `modules_enabled`. Consertar "a config volta atrás
--     sozinha" escrevendo mais config seria repetir o bug com outro número.
--     A decisão de módulos de cada tenant fica exatamente como o admin deixou.
--
-- ═══ ISTO NÃO SUBSTITUI O CUTOVER ═══
--
-- Igual à 128: trata a estrutura de UM caso. A classe inteira de reexecução no
-- boot morre com MIGRATIONS_LEDGER_CUTOVER=1 em produção (#725), gate humano.
--
-- Forward-only: nenhum DROP, nenhum DELETE, nenhum ALTER COLUMN TYPE. Rodar
-- duas vezes produz exatamente o mesmo estado.

ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS schema_name VARCHAR(50);
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS plan VARCHAR(50) DEFAULT 'standard';
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS modules_enabled JSONB DEFAULT '["epi","counting","basic"]';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'tenants_schema_name_key'
          AND table_name = 'tenants'
    ) THEN
        ALTER TABLE public.tenants ADD CONSTRAINT tenants_schema_name_key UNIQUE (schema_name);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_tenants_schema_name ON public.tenants(schema_name);
