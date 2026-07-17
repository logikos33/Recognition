-- 104_inspection_sessions.sql
--
-- Sessões de inspeção da integração monofatura (task-108, ADR-0053):
-- inbound "peça bipada" abre sessão idempotente por (piece_id, stage);
-- outbound (evidência + resultado por atributo + tempo de etapa) é
-- registrado em result JSONB ao fechar a etapa.
--
-- Tabela vive em {tenant_schema}.inspection_sessions (schema-per-tenant,
-- SEM tenant_id — ADR-0004/0016: o schema É o isolamento).
--
-- Duas partes (mesmo padrão de 069 + 075):
--   1. Redefine public.create_tenant_schema() com o CORPO INTEIRO da
--      versão anterior (069) + delta inspection_sessions — novos tenants
--      já nascem com a tabela. Regra append-only: 069 NÃO foi editado.
--      Histórico da função: 024 → 028 → 033 → 069 → 104 (sempre arquivo novo).
--   2. Backfill nos schemas dos tenants EXISTENTES (loop igual ao de 075).
--
-- Idempotência (rodável 2x):
--   CREATE OR REPLACE FUNCTION — idempotente.
--   CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS — no-op se existir.
-- Forward-only: sem DROP, sem ALTER COLUMN TYPE, sem DELETE/TRUNCATE.

-- ============================================================
-- Parte 1 — redefinição de create_tenant_schema (corpo 069 + delta)
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

    -- Inspeções de qualidade (schema completo com todas as colunas — inclui colunas RVB + site_id)
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
        -- Colunas RVB (adicionadas em 033)
        piece_id             UUID,
        validation_type      VARCHAR(10),
        station              VARCHAR(10),
        defect_description   TEXT,
        is_rework            BOOLEAN DEFAULT false,
        rework_attempt       INT DEFAULT 0,
        photo_raw_path       VARCHAR(500),
        photo_raw_r2_key     VARCHAR(500),
        -- Coluna edge (adicionada em 069)
        site_id              UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL,
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

    -- Segmentos de gravação contínua de qualidade (inclui site_id — adicionado em 069)
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
        -- Coluna edge (adicionada em 069)
        site_id          UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Configuração por câmera de qualidade (inclui colunas RVB)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_camera_config (
        id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id                 UUID UNIQUE NOT NULL,
        is_setup_mode             BOOLEAN DEFAULT false,
        product_type              VARCHAR(100),
        production_order          VARCHAR(100),
        ok_confidence_threshold   FLOAT DEFAULT 0.75,
        nok_confidence_threshold  FLOAT DEFAULT 0.65,
        inspection_cooldown_ms    INT DEFAULT 500,
        reference_snapshot_r2_key TEXT,
        -- Colunas RVB (adicionadas em 033)
        inspection_mode           VARCHAR(20) DEFAULT ''continuous'',
        station                   VARCHAR(10),
        camera_type               VARCHAR(20) DEFAULT ''general'',
        validation_types          TEXT[] DEFAULT ''{}'',
        capture_frames_count      INT DEFAULT 5,
        voting_threshold          FLOAT DEFAULT 0.6,
        created_at                TIMESTAMPTZ DEFAULT NOW(),
        updated_at                TIMESTAMPTZ DEFAULT NOW()
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

    -- Frames extraídos de clips para anotação manual
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

    -- Sugestões de retreino geradas pelo feedback
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_retrain_suggestions (
        id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        inspection_id      UUID NOT NULL,
        camera_id          UUID NOT NULL,
        clip_r2_key        TEXT,
        status             VARCHAR(30) DEFAULT ''pending'',
        included_in_job_id UUID,
        created_at         TIMESTAMPTZ DEFAULT NOW()
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

    -- Métricas de CEP por câmera
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

    -- State machine de peças no fluxo RVB (adicionada em 033)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_pieces (
        id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        piece_number              VARCHAR(50) NOT NULL,
        work_order                VARCHAR(50),
        product_type              VARCHAR(100),
        status                    VARCHAR(30) DEFAULT ''idle''
            CHECK (status IN (
                ''idle'',''identified'',
                ''validating_v1'',''rework_v1'',
                ''validating_v2'',''rework_v2'',
                ''waiting_bench_b'',
                ''validating_v3'',''rework_v3'',
                ''approved'',''rejected''
            )),
        current_station           VARCHAR(10)
            CHECK (current_station IN (''bench_a'',''bench_b'')),
        operator_id               UUID,
        started_at                TIMESTAMPTZ DEFAULT NOW(),
        completed_at              TIMESTAMPTZ,
        total_rework_count        INT DEFAULT 0,
        total_rework_time_seconds INT DEFAULT 0,
        photo_quality_path        VARCHAR(500),
        photo_quality_r2_key      VARCHAR(500),
        wiser_exported            BOOLEAN DEFAULT false,
        wiser_exported_at         TIMESTAMPTZ,
        created_at                TIMESTAMPTZ DEFAULT NOW(),
        updated_at                TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Histórico de retrabalho por peça (adicionada em 033)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_reworks (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        piece_id            UUID NOT NULL,
        inspection_id       UUID,
        validation_type     VARCHAR(10) NOT NULL,
        defect_type         VARCHAR(100),
        defect_description  TEXT,
        photo_before_path   VARCHAR(500),
        photo_before_r2_key VARCHAR(500),
        photo_after_path    VARCHAR(500),
        photo_after_r2_key  VARCHAR(500),
        operator_id         UUID,
        started_at          TIMESTAMPTZ DEFAULT NOW(),
        completed_at        TIMESTAMPTZ,
        duration_seconds    INT,
        attempt_number      INT DEFAULT 1,
        notes               TEXT,
        created_at          TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Log de exportações para o sistema Wiser (adicionada em 033)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_wiser_exports (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        piece_id       UUID NOT NULL,
        export_method  VARCHAR(20) DEFAULT ''file_share'',
        file_path      VARCHAR(500),
        api_response   TEXT,
        exported_at    TIMESTAMPTZ DEFAULT NOW(),
        success        BOOLEAN DEFAULT true,
        error_message  TEXT
    )', p_schema_name);

    -- Configuração de bancadas de validação (adicionada em 033)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_stations (
        id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        station_code            VARCHAR(10) NOT NULL UNIQUE,
        name                    VARCHAR(100),
        description             TEXT,
        current_piece_id        UUID,
        camera_ids              JSONB DEFAULT ''[]'',
        tower_controller_type   VARCHAR(20) DEFAULT ''simulated'',
        tower_controller_config JSONB DEFAULT ''{}'',
        tablet_url              VARCHAR(200),
        is_active               BOOLEAN DEFAULT true,
        created_at              TIMESTAMPTZ DEFAULT NOW(),
        updated_at              TIMESTAMPTZ DEFAULT NOW()
    )', p_schema_name);

    -- Sessões de inspeção da integração monofatura (adicionada em 104 — task-108, ADR-0053)
    -- Idempotência inbound: UNIQUE (piece_id, stage) — bipagem repetida não duplica sessão.
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.inspection_sessions (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        piece_id        TEXT NOT NULL,
        stage           TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT ''open'',
        camera_id       UUID,
        started_at      TIMESTAMPTZ DEFAULT NOW(),
        finished_at     TIMESTAMPTZ,
        result          JSONB,
        evidence_r2_key TEXT,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (piece_id, stage)
    )', p_schema_name);

    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS idx_inspection_sessions_piece ON %I.inspection_sessions (piece_id)',
        p_schema_name
    );
    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS idx_inspection_sessions_status ON %I.inspection_sessions (status)',
        p_schema_name
    );

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

-- ============================================================
-- Parte 2 — backfill nos schemas dos tenants existentes
-- (mesmo padrão de loop de 075; idempotente via IF NOT EXISTS)
-- ============================================================

DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT schema_name
        FROM public.tenants
        WHERE schema_name IS NOT NULL
          AND schema_name <> ''
          AND schema_name <> 'public'
    LOOP
        IF NOT EXISTS (
            SELECT FROM information_schema.schemata WHERE schema_name = r.schema_name
        ) THEN
            CONTINUE;
        END IF;
        EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.inspection_sessions (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            piece_id        TEXT NOT NULL,
            stage           TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT ''open'',
            camera_id       UUID,
            started_at      TIMESTAMPTZ DEFAULT NOW(),
            finished_at     TIMESTAMPTZ,
            result          JSONB,
            evidence_r2_key TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (piece_id, stage)
        )', r.schema_name);
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_inspection_sessions_piece ON %I.inspection_sessions (piece_id)',
            r.schema_name
        );
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_inspection_sessions_status ON %I.inspection_sessions (status)',
            r.schema_name
        );
    END LOOP;
END $$;
