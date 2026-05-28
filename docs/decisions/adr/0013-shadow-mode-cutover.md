# ADR-0013: Shadow Mode e Cutover Gradual Edge→Cloud

## Status
Aceito

## Data
2026-05-27

## Contexto

O módulo Quality está em produção ativa com cliente real (documentado em
`docs/alteracoes/2026-04-19_quality-gate-rvb.md`). Seis Celery tasks classificadas
como EDGE rodam no cloud hoje:

- `inference_loop`, `start_hls_stream` — EPI
- `quality_inference_loop`, `run_quality_gate_inspection` — Quality
- `record_quality_camera`, `capture_reference_snapshot` — Quality recording

O plano original de edge deployment não especifica como fazer o cutover dessas tasks
do cloud para o edge sem interromper o cliente em produção.

Regra de ouro estabelecida por Vitor: **cloud Quality NUNCA para de funcionar
pro cliente atual em produção até validação completa do edge.**

## Decisão

**Shadow mode com cutover gradual por câmera.**

### Fase 1 (adição ao plano original): Migrations de suporte

**`046_event_origin.sql`:**
```sql
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS origin VARCHAR(20) DEFAULT 'cloud';
ALTER TABLE camera_events ADD COLUMN IF NOT EXISTS origin VARCHAR(20) DEFAULT 'cloud';
ALTER TABLE counting_events ADD COLUMN IF NOT EXISTS origin VARCHAR(20) DEFAULT 'cloud';
-- Valores: 'cloud', 'edge'
-- Permite distinguir origem de eventos durante shadow period
```

**`047_processing_mode.sql`:**
```sql
ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS processing_mode VARCHAR(20) DEFAULT 'cloud';
ALTER TABLE ip_cameras ADD CONSTRAINT chk_processing_mode
    CHECK (processing_mode IN ('cloud', 'shadow', 'edge'));
-- 'cloud': processado pelo Celery cloud (padrão atual)
-- 'shadow': processado por ambos cloud E edge em paralelo
-- 'edge': processado só pelo edge (pós-validação)
```

### Fases 0–5 (BUILD)
As 6 tasks EDGE continuam rodando no cloud Celery sem alteração.
Novos serviços em `services/inference/` desenvolvidos em paralelo,
sem receber tráfego real.

### Fase 6 (SHADOW) — Paralelo à Fase 6 do plano
Quando edge stack estiver deployado na RVB:

1. Definir câmeras de teste com `processing_mode = 'shadow'`
2. Ambos cloud E edge processam as mesmas câmeras
3. Eventos cloud: `origin = 'cloud'`, eventos edge: `origin = 'edge'`
4. Dashboard de comparação: detecções/min, latência, false positives
5. Mínimo 7 dias de shadow sem anomalias antes de cutover
6. Critério: diferença de detecções < 5% entre cloud e edge

### Fase 6.5 (CUTOVER POR CÂMERA) — Nova fase entre Fase 6 e Fase 7
Após validação do shadow:

1. Câmera por câmera: `UPDATE ip_cameras SET processing_mode = 'edge' WHERE id = ?`
2. Cloud deixa de processar câmeras com `processing_mode = 'edge'`
3. Monitoramento de alertas nos primeiros 30min após cada câmera
4. Rollback instantâneo: `UPDATE ip_cameras SET processing_mode = 'cloud' WHERE id = ?`
5. Completar cutover de todas as câmeras RVB

### Pós-RVB Go-Live (FORA DO PLANO ATUAL)
Após 30 dias de todas as câmeras RVB em `processing_mode = 'edge'` sem incidente:
- Planejamento do desligamento físico das tasks Celery EDGE
- Sprint separada, não parte deste deployment

## Alternativas Consideradas

### A: Cutover imediato (big bang)
- Prós: simples
- Contras: alto risco — se edge falhar, cliente perde detecções em produção; sem rollback fácil

### B: Blue-green por serviço
- Prós: isolamento limpo
- Contras: complexidade operacional alta; requer load balancer no edge

### C: Shadow mode + cutover por câmera **(ESCOLHIDA)**
- Prós: validação gradual, rollback granular (por câmera), cliente não percebe mudança
- Contras: período de processamento duplicado (custo de compute ~2x durante shadow)

## Consequências

### Positivas
- Zero risco de interrupção para cliente em produção
- Validação quantitativa (diff de detecções) antes de cada cutover
- Rollback em 1 UPDATE se algo der errado
- Histórico completo de eventos por origem para auditoria

### Negativas
- Durante shadow period (~7+ dias): custo de compute duplicado (cloud + edge)
- Complexidade adicional no monolito: tasks EDGE precisam checar `processing_mode`

### Neutras
- Migrations 046 e 047 são puramente aditivas (ADD COLUMN IF NOT EXISTS)
- `processing_mode` default `'cloud'` — sem impacto em câmeras existentes

## Implementação

### Modificação nas tasks EDGE durante shadow period

```python
# Exemplo em inference_loop — verificar processing_mode antes de processar
def should_process_on_cloud(camera_id: str) -> bool:
    mode = get_camera_processing_mode(camera_id)  # cache Redis
    return mode in ('cloud', 'shadow')

# Se mode == 'edge': não processa no cloud Celery
# Se mode == 'shadow': processa no cloud E edge em paralelo
# Se mode == 'cloud': processa só no cloud (atual)
```

### Dashboard de comparação shadow

Endpoint sugerido (Fase 6):
```
GET /api/v1/admin/shadow/comparison?site_id=rvb-blumenau-01&hours=24
Response: { cloud_events, edge_events, diff_pct, cameras_in_shadow }
```

## Referências
- OQ-003 em `docs/decisions/open-questions.md`
- `docs/decisions/celery-tasks-migration.md` — classificação completa das 21 tasks
- EDGE_DEPLOYMENT_PLAN.md — Fases 1, 6, 6.5 atualizadas
