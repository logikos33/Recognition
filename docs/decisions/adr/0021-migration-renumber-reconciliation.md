# ADR-0021 — Renumeração de migrations 050–064 para resolver colisão com produção

**Status:** Aceito  
**Data:** 2026-06-23  
**Contexto:** `fix/migration-reconciliation` → merge em `develop`  
**Relacionados:** ADR-0016 (edge-tables-placement), ADR-0018 (counting-deepsort-rebuild)

---

## Contexto

Ao tentar promover `develop → staging` (deploy de produção), o runner de migrations
detectou colisão: a versão `"050"` já estava marcada em `schema_migrations` (aplicada
pelo branch `staging` como `050_loading_sessions_fields.sql` — campos de carga/descarga),
e a versão `"051"` como `051_platform_limits_claim_codes.sql`.

O runner usa `filename.split("_")[0]` como chave de rastreamento. Portanto, ambos os
arquivos de develop (`050_edge_sites.sql`, `051_device_tokens.sql`) seriam silenciosamente
ignorados. A migration `052_site_id_attribution.sql` (primeira não-marcada) falharia ao
tentar `REFERENCES public.edge_sites(id)` em uma tabela que nunca foi criada.

**Resultado:** deploy quebraria o startup da API na migration 052.

---

## Opções avaliadas

### Opção A — Band-aid: pré-criar edge_sites/device_tokens manualmente em prod

**Prós:**
- Rápido — desbloquearia o A8 imediatamente
- Sem alteração de arquivos no repositório (além de documentação)

**Contras:**
- `schema_migrations` em prod ficaria permanentemente "mentindo": versão "050" marcada
  mas associada a `loading_sessions_fields`, não a `edge_sites`
- Drift documentado mas nunca corrigido se não houver migration de reconciliação futura
- Requer intervenção manual no BD de prod (risco humano, janela de manutenção)
- Qualquer novo ambiente (staging-2, dev fresh) ficaria inconsistente

### Opção B — Durável: renumerar 050–064 para 065–079 (escolhida)

**Prós:**
- Resolve o problema de forma permanente e forward-only
- Sem intervenção manual no BD de prod
- Harness e CI continuam funcionando (ambos usam glob dinâmico)
- Qualquer novo ambiente criado do zero receberá todas as migrations na ordem correta
- `schema_migrations` fica consistente: versões "065"–"079" marcadas pelos arquivos corretos

**Contras:**
- Renomear 15 arquivos de migration + 1 arquivo de testes
- Qualquer PR aberto com referência a esses arquivos precisa ser rebased
- Números 050–064 ficam "buracos" no develop (mas já eram colisão — não é regressão)

**Decisão: Opção B.**

O custo de manutenção da opção A (drift documentado permanente, risco de novos
ambientes inconsistentes, intervenção manual em prod) supera o custo pontual da
renumeração. A opção B é forward-only, idempotente e alinhada com o Migration Protocol
do CLAUDE.md.

---

## Implementação

Arquivos renomeados (git mv — histórico preservado):

| Antes | Depois |
|-------|--------|
| `050_edge_sites.sql` | `065_edge_sites.sql` |
| `051_device_tokens.sql` | `066_device_tokens.sql` |
| `052_site_id_attribution.sql` | `067_site_id_attribution.sql` |
| `053_edge_heartbeats.sql` | `068_edge_heartbeats.sql` |
| `054_create_tenant_schema_site_id.sql` | `069_create_tenant_schema_site_id.sql` |
| `055_edge_events.sql` | `070_edge_events.sql` |
| `056_edge_commands.sql` | `071_edge_commands.sql` |
| `057_site_gateways.sql` | `072_site_gateways.sql` |
| `058_notification.sql` | `073_notification.sql` |
| `059_detection_feedback.sql` | `074_detection_feedback.sql` |
| `060_camera_hardening_fields.sql` | `075_camera_hardening_fields.sql` |
| `061_tenant_branding.sql` | `076_tenant_branding.sql` |
| `062_events_search_indexes.sql` | `077_events_search_indexes.sql` |
| `063_counting_sessions_plate.sql` | `078_counting_sessions_plate.sql` |
| `064_retention_days.sql` | `079_retention_days.sql` |

`services/api/tests/security/test_edge_schema.py`: referências atualizadas de 050–054
para 065–069.

---

## Comportamento após o deploy

| Versão em prod | Arquivo em develop | Ação do runner |
|---------------|-------------------|----------------|
| "001"–"049" | `001_*` – `049_*` | SKIP (já aplicado) |
| "050" | *(arquivo não existe em develop)* | SKIP (versão já marcada) |
| "051" | *(arquivo não existe em develop)* | SKIP (versão já marcada) |
| *(não marcado)* | `065_edge_sites.sql` | **RUN** → cria edge_sites |
| *(não marcado)* | `066_device_tokens.sql` | **RUN** → cria enrollment_tokens, device_tokens |
| *(não marcado)* | `067_site_id_attribution.sql` | **RUN** → site_id em cameras/alerts/etc. |
| *(não marcado)* | `068`–`079` | **RUN** → edge infra completa |

---

## Lição registrada (para evitar recorrência)

> **O próximo número de migration deve partir do máximo aplicado entre TODOS os ambientes
> (produção inclusive), nunca só do que está no develop.**

Regra prática: antes de criar uma nova migration, rodar em prod (ou consultar o humano):
```sql
SELECT MAX(CAST(version AS INTEGER)) FROM schema_migrations;
```
O próximo arquivo deve usar `MAX + 1`. Nunca assumir que o develop é o ambiente com
versão mais alta.

Adicionar ao checklist de Migration Protocol do CLAUDE.md:
- Checar `MAX(version)` em prod antes de numerar migration nova

---

## Consequências

- Migrations 065–079 **não aplicadas em prod ainda** — serão aplicadas no primeiro
  deploy pós-merge do `fix/migration-reconciliation` em `develop` e subsequente
  promoção `develop → staging`.
- Staging-only columns (`bay_id`, `truck_plate`, etc. em `counting_sessions`) continuam
  em prod — develop não as remove; são nullable e não causam erros.
- `device_claim_codes` (staging 051) continua em prod — develop não a usa diretamente;
  coexiste sem conflito.
- Próxima migration numerada: **080**.
