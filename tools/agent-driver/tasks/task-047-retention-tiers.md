# task-047 — Tiers de retenção configuráveis por câmera/tenant (R2 lifecycle)

**risk:security** (política de expiração/exclusão de dados + LGPD)
**modo:** AUTO (pausa na review de segurança — esperado)

## Objetivo
Expor no frontend a retenção de frames/clipes por câmera (ou tenant) em tiers — 1, 7, 30, 90
dias — com expiração automática no R2. Vira linha de receita (cliente paga mais por reter mais)
e argumento de conformidade ("guardamos só o necessário").

## Por que (Camerite)
A Camerite vende storage em nuvem como o core, com tiers de 1 dia a 1 ano, escalando por nº de
câmeras. Já temos R2 (boto3); falta a camada de política + expiração + exposição no front.

## Escopo
### Backend (`services/api`)
- **Verificar** o `R2Storage` atual e os prefixos usados (frames/clips por tenant/câmera).
- Campo de retenção: `retention_days` em `{schema}.cameras` (default herdado do tenant). Verificar
  se já existe antes de criar.
- Configuração no tenant: `tenant_settings.feature_flags`/settings já existe (JSONB) — guardar
  `default_retention_days`.
- Expiração: preferir **R2/S3 lifecycle rules** por prefixo (sem job manual). Se não suportado no
  nível de granularidade, um job Celery diário que apaga objetos além do tier. **NUNCA** apagar
  fora do escopo do tenant/câmera; logar contagem do que foi expirado.
- Endpoints: `GET/PUT /api/cameras/<id>/retention` e `GET/PUT /api/tenant/retention` (role-gated).

### Frontend
- Seletor de tier na config da câmera + default do tenant. Avisar impacto (custo/conformidade).

## Fora de escopo
- Cobrança/billing real por tier (só o controle técnico de retenção).
- Retenção de 1 ano / arquivamento frio (fase 2).

## Critérios de aceite
- Mudar o tier de uma câmera passa a expirar objetos no prazo (validar em staging com prazo curto).
- Exclusão estritamente escopada por tenant/câmera; auditável em log.
- Default do tenant aplicado a câmeras novas.
- Testes: política calcula corretamente a data de corte; nada fora do escopo é apagado.

## Migration
Aditiva se `retention_days` não existir: `ADD COLUMN IF NOT EXISTS retention_days INT` em
`%I.cameras` com loop de backfill por tenant (padrão da migration 060). Idempotente.
