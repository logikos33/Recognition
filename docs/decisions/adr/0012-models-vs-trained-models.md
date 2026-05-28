# ADR-0012: Tabela canônica de modelos — `models` vs `trained_models`

## Status
Aceito

## Data
2026-05-27

## Contexto

Coexistem duas tabelas de modelos no schema atual:

**`trained_models`** (migration 003, schema V1):
- Scoped por `user_id` (não `tenant_id`) — padrão antigo, pré-multi-tenant
- Referencia `training_jobs(id)` via `job_id`
- Campos: `model_path`, `map50`, `precision`, `recall`, `is_active`
- Usado por: `dashboard/routes.py` (COUNT queries), `training_repository.py`

**`models`** (migration 007 + 024 + 028 + 033, schema V2):
- Scoped por `tenant_id` — multi-tenant correto
- Campos: `name`, `module`, `version`, `r2_key`, `hub_model_id`, `metrics` (JSONB), `active`
- Usado por: `quality_inference.py`, câmeras (`PUT /api/v1/cameras/<id>/model`), modelo ativo por módulo

**Bug encontrado durante diagnóstico:** `quality_inference.py:90` referencia tabela `training_models` — nome que não existe. Deve ser `models`.

O plano de edge deployment requer uma tabela de modelos canônica para:
- Edge manifest endpoint (`GET /api/v1/edge/models/manifest`)
- Download URLs por modelo (`GET /api/v1/edge/models/{model_id}/download-url`)
- Hot-swap de modelos no edge

## Decisão

**`models` é a tabela canônica daqui pra frente.**

Justificativas:
1. É multi-tenant (`tenant_id` em vez de `user_id`)
2. Tem módulo explícito (`module`: epi, fueling, quality)
3. Tem `r2_key` para download direto — necessário para edge manifest
4. Já é usada por câmeras e quality ativamente
5. `hub_model_id` conecta ao Ultralytics Hub (pipeline de treino atual)

`trained_models` permanece existindo como resultado de training jobs legacy, **sem remoção planejada neste deployment**.

## Bug Fix Imediato

`quality_inference.py:90` (Pre-1, antes da Fase 0):
```python
# ANTES (errado — tabela não existe):
cur.execute("SELECT r2_key FROM training_models WHERE id = %s", (model_id,))

# DEPOIS (correto):
cur.execute("SELECT r2_key FROM models WHERE id = %s", (model_id,))
```

Commit: `fix(quality): corrigir referência tabela training_models → models`

## Alternativas Consideradas

### A: `trained_models` como canônica
- Prós: mais usada em código legacy
- Contras: user-scoped (não multi-tenant), sem `module`, sem `r2_key`, não conecta ao pipeline atual

### B: Nova tabela unificada
- Prós: design limpo
- Contras: migration complexa com backfill, risco em produção, work desnecessário quando `models` já existe

### C: `models` como canônica **(ESCOLHIDA)**
- Prós: multi-tenant, tem todos os campos necessários para edge, já em uso
- Contras: `trained_models` fica "orphaned" (resolvido: deixar como legacy)

## Consequências

### Positivas
- Edge manifest endpoint usa `models` diretamente — sem nova tabela
- Bug em `quality_inference.py` identificado e corrigido antes de ir pra produção

### Negativas
- `trained_models` fica "orphaned" — consumida pelo dashboard legacy mas não atualizada por novos treinos
- Dashboard `COUNT(*) FROM trained_models` pode ficar desatualizado no futuro

### Neutras
- Sprint futura pode unificar se necessário — não bloqueia agora

## Implementação

Para o edge manifest (Fase 2):
```python
# Edge manifest lê de models WHERE active = true AND tenant_id = g.tenant_id
cur.execute("""
    SELECT id, name, module, version, r2_key, metrics
    FROM models
    WHERE tenant_id = %s AND active = true
""", (g.tenant_id,))
```

## Referências
- OQ-004 em `docs/decisions/open-questions.md`
- Pre-1 fix em `docs/decisions/initial-assessment.md`
