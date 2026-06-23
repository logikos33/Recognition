-- 058_notification.sql
--
-- Entrega de alertas a canais externos (WhatsApp/Telegram/email/webhook) — melhoria A / task-042.
-- SEGREDO: 'config' guarda escopo/referência; o token NÃO vai em claro aqui (secret store/env).
-- alert_ref é TEXT (alertas vivem em {schema}.alerts — sem FK cross-schema).
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS. Sem DROP.

CREATE TABLE IF NOT EXISTS public.notification_channels (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN ('whatsapp','telegram','email','webhook')),
    config      JSONB NOT NULL DEFAULT '{}',
    recipients  JSONB NOT NULL DEFAULT '[]',
    enabled     BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notification_channels_tenant ON public.notification_channels (tenant_id);

CREATE TABLE IF NOT EXISTS public.notification_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    channel_id  UUID REFERENCES public.notification_channels(id) ON DELETE SET NULL,
    alert_ref   TEXT,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','sent','failed')),
    dedup_key   TEXT,
    error       TEXT,
    sent_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notification_log_tenant ON public.notification_log (tenant_id);

-- Reenvio não duplica (idempotência por tenant).
CREATE UNIQUE INDEX IF NOT EXISTS uniq_notification_log_dedup
    ON public.notification_log (tenant_id, dedup_key) WHERE dedup_key IS NOT NULL;
