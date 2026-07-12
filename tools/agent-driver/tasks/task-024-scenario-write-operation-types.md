---
title: "Escrita de cenário + 3 operation-types (epi_zone, defect_trigger, counting_line)"
pr_title: "feat(scenarios): operation-types epi_zone/defect_trigger/counting_line + escrita validada"
commit_message: "feat(scenarios): 3 operation-types registrados + escrita de config validada por câmera"
eval: default
budget_minutes: 75
risk: security
---

# Tarefa 024 — Escrita de cenário + os 3 operation-types da RVB

## Objetivo
Registrar os 3 operation-types das frentes da RVB no framework `op_class` (com schema/validação de `config`)
e permitir escrever/atualizar a operação (config) por câmera via o CRUD de `operations` existente. Configura
detecção → `risk: security`. Tabelas existentes. Sem hardware, sem migration. Ver `PLATAFORMA_CENARIOS.md` §2.

## Contexto (LER — C-04, C-01)
- operations/routes.py (CRUD + op_class.validate_config + hot-reload via Redis), module_classes, app/core/auth.
- task-022 (catálogo de operation-types). _helpers_tenant + fixture Postgres efêmero (padrão PR #25).

## Operation-types (cada um = classe registrada com schema de config + validação)
- `epi_zone`: { zona (polígono), classes a vigiar (subset de EpiClass) } → alerta se classe "no_*" na zona.
- `defect_trigger`: { ROI da esteira, gatilho, classes de defeito } → inspeção + (OCR/contagem ficam no edge).
- `counting_line`: { linha (2 pontos), direção, classe='person' } → contagem de cruzamentos (DeepSORT).

## Comportamento
- Validar o `config` contra o schema do type (geometria coerente, classes válidas do módulo). Inválido → 400.
- tenant_id do JWT; câmera/operação de outro tenant → 404. Versionar (incrementa version) + sinalizar hot-reload.

## Eval (default, banco REAL)
- criar operação de cada type com config válida → persistida + versionada; config inválida (geometria/classe) → 400.
- isolamento: escrever em câmera de outro tenant → 404; cross-tenant (helper).
- validate_config rejeita: polígono <3 pontos, linha ≠2 pontos, classe fora do módulo.
- ruff + pytest (DB real) + tsc verdes.

## Critérios de aceitação
- [ ] 3 operation-types registrados com schema+validação; escrita tenant-scoped (C-01); versão+hot-reload.
- [ ] Testes contra Postgres REAL cobrindo válido/ inválido/ cross-tenant. PR para develop.

## NEEDS CLARIFICATION
- Confirmar no código como o hot-reload via Redis é sinalizado hoje (operations update) e reusar — não inventar canal novo.

## Checkpoint
- Só PR (humano revisa — configura detecção, risk security). Sem produção. Sem migration.
