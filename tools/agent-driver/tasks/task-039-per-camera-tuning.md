---
title: "Tuning por câmera: confidence + máscaras + perfil dia/noite (contenção falso-positivo)"
pr_title: "feat(scenarios): tuning por câmera — confidence, exclude-zones e perfil dia/noite no editor"
commit_message: "feat(scenarios): exclude_zones + day_night_profile na config de operação + UI no editor"
eval: default
budget_minutes: 90
risk: security
---

# Tarefa 039 — Tuning por câmera · contenção R5 (falsos-positivos em escala)

## Objetivo
Pesquisa: falso-positivo em escala vem de IR/insetos, sombra, folhagem — e exige tunagem POR CÂMERA. Conter com
o que já temos na `config` de operação: **confidence** (já existe), **exclude_zones** (máscaras a ignorar) e
**perfil dia/noite** (thresholds distintos). Expor no editor visual (task-023). Cloud + front, sem hardware, sem
migration (tudo em `config` JSONB validada por op_class). Ver CONTENCAO_RISCOS_ESCALA.md (R5).

## Contexto (LER antes — C-04)
- operations/canonical/{epi_zone,defect_trigger,counting_line}.py — config_schema + validate_config + evaluate.
- apps/frontend editor de cenário (task-023, overlay de desenho); harness Vitest/Playwright (task-021).

## Comportamento
- Config (nos op-types relevantes): `exclude_zones` (lista de polígonos a IGNORAR) e `day_night_profile`
  (ex: `{"day":{"confidence":0.5},"night":{"confidence":0.7}}`). validate_config valida geometria/limites; defaults
  preservam comportamento.
- evaluate: descartar detecção cujo centro cai em `exclude_zones`; escolher threshold por período se houver perfil.
- Front: ferramenta de **máscara** (desenhar zona de exclusão) + campos de confidence dia/noite; testar (UX + e2e).

## Arquivos
- services/api/app/domain/services/operations/canonical/*.py (config + evaluate)
- apps/frontend/ (editor: máscara + campos dia/noite + testes Vitest/Playwright)
- services/api/tests/...

## Eval (default + harness de front 021) — testes SÃO o critério
- detecção dentro de exclude_zone é descartada; perfil noite aplica threshold maior (casos sintéticos).
- editor desenha máscara e salva via operations API; e2e desenhar→salvar→persistir.
- validate_config rejeita geometria inválida; ruff + pytest + tsc verdes.

## Critérios de aceitação
- [ ] exclude_zones + day_night_profile na config + validação + evaluate; UI no editor com testes. PR para develop.

## Checkpoint
- Só PR (humano revisa — config de detecção + front). Sem produção. Sem migration.
