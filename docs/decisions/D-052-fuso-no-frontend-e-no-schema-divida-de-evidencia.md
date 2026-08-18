# D-052 · Fuso no frontend e no schema — dívida de evidência

**Seção:** 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (achado) · 📌 dívida**

Auditoria do item 4: **nenhuma** tela do frontend fixa `America/Sao_Paulo` — todas usam
`toLocaleString('pt-BR')`, que converte para o fuso do **navegador/kiosk** (não há lib tz nem util
canônico). Pior: `public.alerts` é `TIMESTAMP` **ingênuo** (`infra/migrations/004_cameras_alerts.sql`) e é
serializado sem offset (`events/routes.py:88` `.isoformat()`) → `new Date()` no browser interpreta como
hora local → **erro silencioso de ~3h** nas telas de alerta/evento (`AlertsHistoryPage`, `InvestigationPage`,
`AlertsPanel`, `MonitoringPage`, `KPIRow`). As tabelas novas e a auditoria (`audit_log`,
`tenant_context_audit`) já são `timestamptz` — corretas. **Não corrigir às pressas** (ALTER COLUMN TYPE é
proibido). Plano: (a) criar util canônico `formatDateTime` com `Intl.DateTimeFormat('pt-BR',{timeZone:
'America/Sao_Paulo'})` e aplicar nas telas de evento/alerta/auditoria; (b) forçar `Z`/UTC na serialização
de colunas ingênuas; (c) padronizar novas colunas em `timestamptz`.
