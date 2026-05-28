-- 024_tenant_schema_function.sql
-- Cria função para provisionar schema por tenant e inicializa schemas admin e rvb.
-- Idempotente — seguro rodar múltiplas vezes.

-- Função principal: cria schema + tabelas isoladas por tenant
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
        -- schedule_rules: array de objetos com days, start, end, module
        -- Ex: [{"days":[1,2,3,4,5],"start":"08:00","end":"18:00","module":"epi"}]
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

    -- Jobs de treinamento
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

    -- Inspeções de qualidade (módulo quality)
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.quality_inspections (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id UUID,
        result VARCHAR(10),
        defect_class VARCHAR(100),
        confidence FLOAT,
        evidence_r2_key TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
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

    -- Tabela extra para tenant admin: suporte tickets (fase 2)
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

-- Criar schema admin (Logikos)
SELECT public.create_tenant_schema('admin');

-- Criar schema rvb (primeiro cliente)
SELECT public.create_tenant_schema('rvb');
