-- 028_quality_module.sql
-- Módulo de Qualidade Industrial — novas tabelas e extensão de quality_inspections.
-- Idempotente — seguro rodar múltiplas vezes.
-- Estratégia: itera todos os schemas de tenant em public.tenants e aplica DDL por schema.

-- ============================================================
-- PARTE 1: Extensão de quality_inspections + novas tabelas por tenant
-- ============================================================
DO $$
DECLARE
    r RECORD;
BEGIN
    -- Iterar schemas de todos os tenants cadastrados
    FOR r IN
        SELECT schema_name
        FROM public.tenants
        WHERE schema_name IS NOT NULL
          AND schema_name != ''
    LOOP
        -- Verificar que o schema existe
        IF NOT EXISTS (
            SELECT FROM information_schema.schemata
            WHERE schema_name = r.schema_name
        ) THEN
            CONTINUE;
        END IF;

        -- ---------------------------------------------------------
        -- Estender quality_inspections (já existe via create_tenant_schema)
        -- ---------------------------------------------------------
        IF EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = r.schema_name
              AND table_name = 'quality_inspections'
        ) THEN
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS defect_category   VARCHAR(50)',   r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS defect_subtype    VARCHAR(100)',  r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS piece_sequence_id BIGINT',        r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS production_order  VARCHAR(100)',  r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS product_type      VARCHAR(100)',  r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS shift             VARCHAR(20)',   r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS clip_r2_key       TEXT',          r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS clip_start        TIMESTAMPTZ',  r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS clip_end          TIMESTAMPTZ',  r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS clip_status       VARCHAR(30) DEFAULT ''pending''', r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS is_first_ok_of_order BOOLEAN DEFAULT false', r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS rolling_nok_rate_1h  FLOAT', r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS rolling_nok_rate_8h  FLOAT', r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS is_cep_alert      BOOLEAN DEFAULT false', r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS feedback_status   VARCHAR(30) DEFAULT ''pending''', r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS feedback_by       UUID',          r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS feedback_at       TIMESTAMPTZ',  r.schema_name);
            EXECUTE format('ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS feedback_notes    TEXT',          r.schema_name);

            -- Índices de busca frequente
            EXECUTE format('CREATE INDEX IF NOT EXISTS idx_qi_camera_result_%s ON %I.quality_inspections (camera_id, result, created_at DESC)',
                replace(r.schema_name, '-', '_'), r.schema_name);
            EXECUTE format('CREATE INDEX IF NOT EXISTS idx_qi_feedback_%s ON %I.quality_inspections (feedback_status, created_at DESC)',
                replace(r.schema_name, '-', '_'), r.schema_name);
        END IF;

        -- ---------------------------------------------------------
        -- Segmentos de gravação contínua (buffer 48h)
        -- IMPORTANTE: gravação ativa APENAS para cameras com active_module = 'quality'
        -- ---------------------------------------------------------
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quality_recording_segments (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            camera_id        UUID NOT NULL,
            segment_start    TIMESTAMPTZ NOT NULL,
            segment_end      TIMESTAMPTZ NOT NULL,
            duration_seconds INT NOT NULL,
            r2_key           TEXT NOT NULL,
            size_bytes       BIGINT,
            status           VARCHAR(30) DEFAULT ''available'',
            created_at       TIMESTAMPTZ DEFAULT NOW()
        )', r.schema_name);

        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_qrs_camera_time_%s ON %I.quality_recording_segments (camera_id, segment_start DESC)',
            replace(r.schema_name, '-', '_'), r.schema_name);

        -- ---------------------------------------------------------
        -- Configuração por câmera de qualidade
        -- ---------------------------------------------------------
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quality_camera_config (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            camera_id                UUID UNIQUE NOT NULL,
            is_setup_mode            BOOLEAN DEFAULT false,
            product_type             VARCHAR(100),
            production_order         VARCHAR(100),
            ok_confidence_threshold  FLOAT DEFAULT 0.75,
            nok_confidence_threshold FLOAT DEFAULT 0.65,
            inspection_cooldown_ms   INT DEFAULT 500,
            reference_snapshot_r2_key TEXT,
            created_at               TIMESTAMPTZ DEFAULT NOW(),
            updated_at               TIMESTAMPTZ DEFAULT NOW()
        )', r.schema_name);

        -- ---------------------------------------------------------
        -- Snapshots de referência (primeiro OK do lote)
        -- ---------------------------------------------------------
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quality_reference_snapshots (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            camera_id        UUID NOT NULL,
            production_order VARCHAR(100),
            r2_key           TEXT NOT NULL,
            captured_at      TIMESTAMPTZ DEFAULT NOW(),
            captured_by      UUID
        )', r.schema_name);

        -- ---------------------------------------------------------
        -- Frames extraídos de clips para anotação manual
        -- ---------------------------------------------------------
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quality_annotation_frames (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            inspection_id     UUID,
            r2_key            TEXT NOT NULL,
            frame_number      INT NOT NULL,
            timestamp_in_clip FLOAT,
            annotations       JSONB DEFAULT ''[]'',
            annotation_status VARCHAR(30) DEFAULT ''pending'',
            annotated_by      UUID,
            annotated_at      TIMESTAMPTZ,
            created_at        TIMESTAMPTZ DEFAULT NOW()
        )', r.schema_name);

        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_qaf_inspection_%s ON %I.quality_annotation_frames (inspection_id)',
            replace(r.schema_name, '-', '_'), r.schema_name);

        -- ---------------------------------------------------------
        -- Sugestões de retreino geradas pelo feedback
        -- ---------------------------------------------------------
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quality_retrain_suggestions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            inspection_id       UUID NOT NULL,
            camera_id           UUID NOT NULL,
            clip_r2_key         TEXT,
            status              VARCHAR(30) DEFAULT ''pending'',
            included_in_job_id  UUID,
            created_at          TIMESTAMPTZ DEFAULT NOW()
        )', r.schema_name);

        -- ---------------------------------------------------------
        -- Jobs de treinamento do módulo qualidade
        -- ---------------------------------------------------------
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quality_training_jobs (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name                VARCHAR(255),
            status              VARCHAR(50) DEFAULT ''queued'',
            source_type         VARCHAR(30) DEFAULT ''video'',
            hub_dataset_id      VARCHAR(255),
            hub_project_id      VARCHAR(255),
            hub_version_id      VARCHAR(255),
            source_video_r2_key TEXT,
            prompt_description  TEXT,
            frames_extracted    INT DEFAULT 0,
            frames_annotated    INT DEFAULT 0,
            metrics             JSONB DEFAULT ''{}'',
            error_message       TEXT,
            model_r2_key        TEXT,
            active              BOOLEAN DEFAULT false,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW()
        )', r.schema_name);

        -- ---------------------------------------------------------
        -- Métricas de CEP por câmera (base histórica para cálculo de σ)
        -- ---------------------------------------------------------
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quality_cep_baseline (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            camera_id      UUID NOT NULL,
            product_type   VARCHAR(100),
            baseline_date  DATE NOT NULL,
            shift          VARCHAR(20),
            mean_nok_rate  FLOAT,
            stddev_nok_rate FLOAT,
            ucl            FLOAT,
            lcl            FLOAT,
            sample_size    INT,
            calculated_at  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (camera_id, product_type, baseline_date, shift)
        )', r.schema_name);

    END LOOP;
END $$;

-- ============================================================
-- PARTE 2: Tabela pública de auditoria de acesso a vídeos
-- (schema public — fora do isolamento por tenant)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.quality_video_access_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID,
    tenant_schema VARCHAR(50) NOT NULL,
    resource_type VARCHAR(30) NOT NULL,
    resource_id   TEXT NOT NULL,
    ip_address    INET,
    accessed_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qval_user    ON public.quality_video_access_log (user_id, accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_qval_tenant  ON public.quality_video_access_log (tenant_schema, accessed_at DESC);

-- ============================================================
-- PARTE 3: Atualizar create_tenant_schema() para futuros tenants
-- Adicionar todas as tabelas de qualidade ao provisionamento
-- ============================================================
CREATE OR REPLACE FUNCTION public.create_tenant_schema(p_schema_name TEXT)
RETURNS void AS $$
BEGIN
    -- Criar schema (idempotente)
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', p_schema_name);

    -- Câmeras com módulos, agendamento e modelos vinculados
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.cameras (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        location VARCHAR(255),
        rtsp_url TEXT NOT NULL,
        status VARCHAR(50) DEFAULT ''inactive'',
        active_module VARCHAR(50) DEFAULT ''epi'',
        model_epi_id UUID,
        model_quality_id UUID,
        model_counting_id UUID,
        schedule_rules JSONB DEFAULT ''[]'',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Alertas de violação de EPI
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.alerts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id UUID,
        module VARCHAR(50),
        violation_type VARCHAR(100),
        confidence FLOAT,
        evidence_r2_key TEXT,
        acknowledged BOOLEAN DEFAULT false,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Modelos YOLO treinados
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.models (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        module VARCHAR(50) NOT NULL,
        version VARCHAR(50),
        r2_key TEXT,
        hub_model_id VARCHAR(255),
        hub_project_id VARCHAR(255),
        metrics JSONB DEFAULT ''{}'',
        active BOOLEAN DEFAULT false,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Jobs de treinamento (módulo EPI/geral)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.training_jobs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255),
        module VARCHAR(50),
        status VARCHAR(50) DEFAULT ''queued'',
        hub_dataset_id VARCHAR(255),
        hub_project_id VARCHAR(255),
        hub_version_id VARCHAR(255),
        source_video_r2_key TEXT,
        prompt_description TEXT,
        frames_extracted INT DEFAULT 0,
        frames_annotated INT DEFAULT 0,
        metrics JSONB DEFAULT ''{}'',
        error_message TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Inspeções de qualidade (schema completo com todas as colunas)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_inspections (
        id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id            UUID,
        result               VARCHAR(10),
        defect_class         VARCHAR(100),
        defect_category      VARCHAR(50),
        defect_subtype       VARCHAR(100),
        confidence           FLOAT,
        evidence_r2_key      TEXT,
        piece_sequence_id    BIGINT,
        production_order     VARCHAR(100),
        product_type         VARCHAR(100),
        shift                VARCHAR(20),
        clip_r2_key          TEXT,
        clip_start           TIMESTAMPTZ,
        clip_end             TIMESTAMPTZ,
        clip_status          VARCHAR(30) DEFAULT ''pending'',
        is_first_ok_of_order BOOLEAN DEFAULT false,
        rolling_nok_rate_1h  FLOAT,
        rolling_nok_rate_8h  FLOAT,
        is_cep_alert         BOOLEAN DEFAULT false,
        feedback_status      VARCHAR(30) DEFAULT ''pending'',
        feedback_by          UUID,
        feedback_at          TIMESTAMPTZ,
        feedback_notes       TEXT,
        created_at           TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Contagem de pessoas (módulo counting)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.crossings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id UUID,
        direction VARCHAR(10),
        count_in INT DEFAULT 0,
        count_out INT DEFAULT 0,
        period_start TIMESTAMPTZ,
        period_end TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Segmentos de gravação de qualidade
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_recording_segments (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id        UUID NOT NULL,
        segment_start    TIMESTAMPTZ NOT NULL,
        segment_end      TIMESTAMPTZ NOT NULL,
        duration_seconds INT NOT NULL,
        r2_key           TEXT NOT NULL,
        size_bytes       BIGINT,
        status           VARCHAR(30) DEFAULT ''available'',
        created_at       TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Configuração por câmera de qualidade
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_camera_config (
        id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id                UUID UNIQUE NOT NULL,
        is_setup_mode            BOOLEAN DEFAULT false,
        product_type             VARCHAR(100),
        production_order         VARCHAR(100),
        ok_confidence_threshold  FLOAT DEFAULT 0.75,
        nok_confidence_threshold FLOAT DEFAULT 0.65,
        inspection_cooldown_ms   INT DEFAULT 500,
        reference_snapshot_r2_key TEXT,
        created_at               TIMESTAMPTZ DEFAULT NOW(),
        updated_at               TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Snapshots de referência (primeiro OK do lote)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_reference_snapshots (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id        UUID NOT NULL,
        production_order VARCHAR(100),
        r2_key           TEXT NOT NULL,
        captured_at      TIMESTAMPTZ DEFAULT NOW(),
        captured_by      UUID
    )', p_schema_name);

    -- Frames de anotação
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_annotation_frames (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        inspection_id     UUID,
        r2_key            TEXT NOT NULL,
        frame_number      INT NOT NULL,
        timestamp_in_clip FLOAT,
        annotations       JSONB DEFAULT ''[]'',
        annotation_status VARCHAR(30) DEFAULT ''pending'',
        annotated_by      UUID,
        annotated_at      TIMESTAMPTZ,
        created_at        TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Sugestões de retreino
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_retrain_suggestions (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        inspection_id       UUID NOT NULL,
        camera_id           UUID NOT NULL,
        clip_r2_key         TEXT,
        status              VARCHAR(30) DEFAULT ''pending'',
        included_in_job_id  UUID,
        created_at          TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Jobs de treinamento do módulo qualidade
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_training_jobs (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name                VARCHAR(255),
        status              VARCHAR(50) DEFAULT ''queued'',
        source_type         VARCHAR(30) DEFAULT ''video'',
        hub_dataset_id      VARCHAR(255),
        hub_project_id      VARCHAR(255),
        hub_version_id      VARCHAR(255),
        source_video_r2_key TEXT,
        prompt_description  TEXT,
        frames_extracted    INT DEFAULT 0,
        frames_annotated    INT DEFAULT 0,
        metrics             JSONB DEFAULT ''{}'',
        error_message       TEXT,
        model_r2_key        TEXT,
        active              BOOLEAN DEFAULT false,
        created_at          TIMESTAMPTZ DEFAULT NOW(),
        updated_at          TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Métricas CEP
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_cep_baseline (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id       UUID NOT NULL,
        product_type    VARCHAR(100),
        baseline_date   DATE NOT NULL,
        shift           VARCHAR(20),
        mean_nok_rate   FLOAT,
        stddev_nok_rate FLOAT,
        ucl             FLOAT,
        lcl             FLOAT,
        sample_size     INT,
        calculated_at   TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (camera_id, product_type, baseline_date, shift)
    )', p_schema_name);

    -- Tabela extra para tenant admin: suporte tickets
    IF p_schema_name = 'admin' THEN
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.support_tickets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES public.tenants(id),
            subject VARCHAR(255),
            status VARCHAR(50) DEFAULT ''open'',
            priority VARCHAR(20) DEFAULT ''normal'',
            created_by UUID REFERENCES public.users(id),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )', p_schema_name);
    END IF;

END;
$$ LANGUAGE plpgsql;
