# Task 077 — reconciliar cleanups de quality com os tiers de retenção (ADR-0047)

**Status**: ABERTA (backlog) · **Risk**: security (deleção irreversível de dados no R2)
**Relaciona**: ADR-0047 (retention tiers), ADR-0028/0033 (evidência cloud-first R2),
`services/api/app/infrastructure/queue/tasks/quality_cep.py`,
`services/api/app/infrastructure/queue/celery_app.py` (`DEFERRED_BEAT_SCHEDULE`).
**Origem**: descoberto ao curar o `beat_schedule` (PR do serviço Celery Beat).

## Problema

Duas tasks de limpeza estão em `DEFERRED_BEAT_SCHEDULE` — deliberadamente **fora** do schedule
ativo do beat — e NÃO devem ser ligadas sem este trabalho:

- `quality_cep.cleanup_quality_recordings` — apaga segmentos de gravação do R2 com retenção
  **hardcoded** `QUALITY_BUFFER_HOURS=48` (horário).
- `quality_cep.cleanup_quality_clips` — apaga clips de NOK do R2 com retenção **hardcoded**
  `QUALITY_CLIP_RETENTION_DAYS=7` (diário).

Riscos de ligá-las como estão:
1. **Conflito de política**: a retenção hardcoded (48h / 7d) contradiz os **tiers de retenção
   configuráveis** definidos no **ADR-0047** (task-047). Duas fontes de verdade sobre "quando apagar".
2. **Deleção em massa irreversível**: como nunca rodaram, há backlog acumulado no R2. O 1º disparo
   apagaria tudo que exceder 48h/7d de uma vez — `storage.delete_object` é irreversível.

## Escopo do fix

- Fazer os cleanups **respeitarem os tiers do ADR-0047** (retenção por tenant/tier configurável),
  não constantes hardcoded. Considerar unificar com `tasks/retention_expiry.py` (task-047), que já
  modela expiração por tier e hoje **também não está agendada**.
- Definir a política de "primeiro disparo" (ex.: dry-run + relatório do que seria apagado, ou
  janela de graça) para evitar deleção em massa do backlog sem revisão humana.
- Só então mover os cleanups de `DEFERRED_BEAT_SCHEDULE` para `SAFE_BEAT_SCHEDULE` (ou agendar via
  `retention_expiry` unificado).

## Aceite

- Cleanups leem retenção dos tiers do ADR-0047 (sem hardcode 48h/7d).
- Teste falha-antes/passa-depois: com um tier configurado, a task só marca/apaga o que o tier manda.
- Estratégia de 1º disparo documentada (dry-run ou janela de graça) para não apagar backlog às cegas.
- `ruff` + `pytest` verde; PR contra `develop`; **STOP para revisão humana** (risk:security).
