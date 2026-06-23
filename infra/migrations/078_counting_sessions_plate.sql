-- 063 — LPR: campos de placa na sessão de carga/descarga (task-050)
-- Idempotente: ADD COLUMN IF NOT EXISTS; sem DROP; sem ALTER TYPE.
-- plate_text:       placa lida por OCR (ex.: "ABC1D23") ou corrigida manualmente
-- plate_confidence: confiança do OCR [0.0, 1.0]; NULL = lida manualmente
-- plate_review:     TRUE quando confiança < 0.80 → marcada p/ revisão humana
-- plate_manual:     TRUE quando o operador sobrescreveu o OCR
-- Toda nova linha fica com NULL/FALSE — sem backfill (campo opcional).

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS plate_text       TEXT,
    ADD COLUMN IF NOT EXISTS plate_confidence REAL,
    ADD COLUMN IF NOT EXISTS plate_review     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS plate_manual     BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_counting_sessions_plate_text
    ON public.counting_sessions (plate_text)
    WHERE plate_text IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_counting_sessions_plate_review
    ON public.counting_sessions (tenant_id, plate_review)
    WHERE plate_review = TRUE;
