# Quality Module — Status Real

Data: 2026-05-27

## Esclarecimento de terminologia

Quality é um MÓDULO do produto Recognition, junto com EPI e Fueling.
Não é um cliente. O cliente é RVB Isolantes.

## Estado atual (verificado em staging)

- Código: 100% implementado (48 componentes frontend + tabelas quality_*
  + Celery tasks + endpoints REST)
- Documentação: `docs/alteracoes/2026-04-19_quality-gate-rvb.md`
  documenta entrega técnica do módulo, não uso em produção
- Tenants ativos com módulo quality: nenhum em produção real
- Uso real: não há atividade de produção em quality_inspections,
  quality_recording_segments etc com cliente real

## Implicação

RVB será o primeiro tenant a usar o módulo Quality em ambiente real,
como parte do go-live inicial do produto. Edge deployment incorpora
Quality desde o dia 1.

Não há "produção Quality a preservar". Decisões de cutover (ADR-0013)
refletem isso: cutover direto, sem shadow mode.
