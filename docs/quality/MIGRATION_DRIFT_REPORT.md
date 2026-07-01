# Migration Drift Report

**Data:** 2026-06-23  
**Gerado por:** diagnóstico automático (`fix/migration-reconciliation`)  
**Status:** Resolvido via renumeração (ver ADR-0021)

---

## 1. Contexto

`staging` e `develop` divergiram sem common ancestor no git. Ao tentar abrir PR
`develop → staging` (A8), o GitHub sinalizou merge conflict. Investigação revelou
colisão de números de migration entre as duas linhagens.

---

## 2. Mapa completo de migrations

### 2.1 Migrations idênticas (001–049) — sem drift

Ambos os branches têm os mesmos 45 arquivos de 001 a 049 (com gaps 042–045
ausentes em **ambos** — nunca existiram, não é divergência).

```
001 002 003 004 005 006 007 008 009 010
011 012 013 014 015 016 017 018 019 020
021 022 023 024 025 026 027 028 029 030
031 032 033 034 035 036 037 038 039 040
041 [042-045 AUSENTES em ambos] 046 047 048 049
```

### 2.2 Divergência a partir de 050

| Versão | Staging (produção) | Develop (antes do fix) | Impacto no deploy |
|--------|-------------------|------------------------|-------------------|
| **050** | `050_loading_sessions_fields.sql` | `050_edge_sites.sql` | `edge_sites` **NUNCA criada** (skip por version="050") |
| **051** | `051_platform_limits_claim_codes.sql` | `051_device_tokens.sql` | `enrollment_tokens`/`device_tokens` **NUNCA criados** (skip por version="051") |
| 052 | — (não existe) | `052_site_id_attribution.sql` | **FAIL** — REFERENCES `edge_sites` que não existe |
| 053–064 | — | existem | nunca chegam a rodar (o runner para no FAIL da 052) |

### 2.3 Conteúdo das migrations em colisão

**Staging `050_loading_sessions_fields.sql`** (já aplicada em prod):
- `ALTER TABLE public.counting_sessions ADD COLUMN IF NOT EXISTS bay_id UUID`
- `truck_plate TEXT`, `direction TEXT CHECK (IN 'load','unload')`, `expected_count INT`
- `divergence INT`, `video_clip_url TEXT`, `manual_count INT`, `acceptance_status TEXT`
- Índice: `idx_counting_sessions_tenant_bay`

**Staging `051_platform_limits_claim_codes.sql`** (já aplicada em prod):
- `ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS max_seats INT, single_session BOOLEAN, rate_limit_per_minute INT`
- `ALTER TABLE public.plans ADD COLUMN IF NOT EXISTS api_rate_per_minute INT DEFAULT 120`
- `CREATE TABLE IF NOT EXISTS public.device_claim_codes (...)` (hash SHA-256 de claim codes)

---

## 3. Como o runner rastreia (causa raiz)

`infra/migrations/run_migrations.py` rastreia por **prefixo numérico**:

```python
version = filename.split("_")[0]   # "050" para qualquer arquivo que começa com "050"
if version in applied:
    continue                        # SKIP — não importa o nome após o número
```

Portanto: se prod tem version `"050"` marcada (de `loading_sessions_fields`),
o runner ignora `050_edge_sites.sql` silenciosamente. Idem para `"051"`.

---

## 4. Drift adicional detectado

| Tipo | Detalhe |
|------|---------|
| **Gap 042–045** | Ausente em **ambos** os branches — não é drift, nunca foi criado |
| **Staging-only columns** | `counting_sessions.{bay_id, truck_plate, direction, expected_count, divergence, video_clip_url, manual_count, acceptance_status}` existem em prod mas não em develop migrations |
| **Staging-only table** | `public.device_claim_codes` existe em prod (via 051 staging) |
| **Staging-only columns em tenants** | `max_seats`, `single_session`, `rate_limit_per_minute` |
| **Staging-only column em plans** | `api_rate_per_minute` |

**Avaliação de risco das staging-only colunas:** Todas são nullable; develop não as
remove nem as referencia com NOT NULL. O deploy não causará erros de schema nas queries
existentes de develop.

---

## 5. SQL de verificação para o humano rodar em prod (read-only)

```sql
-- 5.1 Versões aplicadas (deve mostrar 001-049, 050, 051)
SELECT version FROM schema_migrations ORDER BY version;

-- 5.2 Verificar se edge_sites NÃO existe (esperado antes do fix)
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'edge_sites'
) AS edge_sites_exists;

-- 5.3 Verificar se device_tokens NÃO existe
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'device_tokens'
) AS device_tokens_exists;

-- 5.4 Confirmar colunas de loading_sessions existem (staging 050)
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'counting_sessions'
  AND column_name IN ('bay_id','truck_plate','direction','expected_count','manual_count')
ORDER BY column_name;

-- 5.5 Confirmar device_claim_codes existe (staging 051)
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'device_claim_codes'
) AS device_claim_codes_exists;
```

---

## 6. Resolução

**Opção escolhida: B — Renumeração** (ver ADR-0021).

Migrations 050–064 de develop renomeadas para 065–079. Após o deploy:
- Runner skipa versions "050"/"051" (já marcadas em prod) ✅
- Runner aplica "065" (`edge_sites`) → tabela criada ✅
- Runner aplica "066" (`device_tokens`) → `enrollment_tokens` + `device_tokens` criadas ✅
- Runner aplica "067"–"079" → sem dependências quebradas ✅

**Migration 080 adicionada:** `080_loading_sessions_compat.sql` representa no develop todo o
schema das staging-only migrations 050/051 (campos de carga/descarga em `counting_sessions`,
colunas de plataforma em `tenants`/`plans`, tabela `device_claim_codes`). Em prod essas colunas
já existem — os `ADD COLUMN IF NOT EXISTS` são no-op. Em ambiente novo o repo é agora
fonte de verdade completa.

**Lição registrada no ADR:** o próximo número de migration deve partir do máximo aplicado
entre **todos** os ambientes (prod inclusive), nunca só do que está no develop.
