# ADR-0013: Cutover direto sem shadow mode

## Status
Aceito

## Data
2026-05-27

## Contexto

Recognition Platform está em estado pre-produção: código completo,
com 41 migrations aplicadas, todos os módulos (EPI, Fueling, Quality)
implementados, mas SEM clientes em produção. RVB Isolantes será o
primeiro tenant a usar o sistema em ambiente real, e o edge deployment
faz parte desse go-live inicial.

Versão anterior deste ADR propunha shadow mode (cloud + edge em
paralelo durante migração) baseado na premissa incorreta de que
havia cliente Quality em produção.

## Decisão

Cutover direto na Fase 3 do EDGE_DEPLOYMENT_PLAN: as 6 tasks Celery
EDGE migram do monolito api-v3 para services/inference/ sem período
de coexistência.

Multi-tenant deployment_mode é suficiente:
- `tenant.deployment_mode='edge'` → inferência via services/inference/
  rodando no Mini PC do cliente
- `tenant.deployment_mode='cloud_only'` (hipotético, sem cliente atual)
  → inferência via services/inference/ rodando no Railway

## Alternativas Consideradas

### Shadow mode com migrations event_origin + processing_mode
- Prós: permitiria rollback granular por câmera
- Contras: complexidade desnecessária sem produção a preservar;
  requer 2 migrations extras (046, 047); requer Fase 6.5 adicional;
  dual deployment durante semanas
- Rejeitada: overhead maior que benefício em contexto greenfield

## Consequências

### Positivas
- Cronograma comprimido (sem Fase 6.5)
- Sem migrations 046 e 047
- Sem complexidade de roteamento dual por câmera
- Plano mais simples de comunicar e executar

### Negativas
- Se um segundo cliente chegar querendo cloud-only após RVB já estar
  em edge, a falta de experiência operacional com dual mode pode
  causar atrito. Mitigação: revisitar este ADR quando segundo
  cliente entrar em pipeline.

### Neutras
- Reverte mudanças que o ADR-0013 anterior havia incorporado ao
  EDGE_DEPLOYMENT_PLAN.md

## Implementação

Conforme Fase 3 do plano: refator dos microsserviços com
INFERENCE_ENGINE selecionável por env var (deepstream para edge,
ultralytics como backend cloud-only).

## Referências
- OQ-003 em `docs/decisions/open-questions.md` (resolvida)
- `docs/decisions/oq-responses.md`
