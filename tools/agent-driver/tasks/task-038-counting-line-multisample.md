---
title: "counting_line: voto majoritário multi-amostra (contenção de contagem)"
pr_title: "feat(operations): counting_line com confirmação multi-amostra + debounce de direção"
commit_message: "feat(operations): voto majoritário N-amostras no cruzamento da linha (reduz ID-switch/oclusão)"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 038 — counting_line multi-amostra · contenção R6

## Objetivo
Pesquisa de campo: contagem por cruzamento de 1 frame degrada (92% detecção → 85% contagem) por ID-switch do
tracker em oclusão. Conter no `counting_line` (op-type já existente, task-024) exigindo **confirmação por N
amostras** antes de contar um cruzamento + **debounce de direção** (não conta vai-e-volta como 2). Cloud, tabela
existente, sem hardware, sem migration. Ver `docs/architecture/CONTENCAO_RISCOS_ESCALA.md` (R6).

## Contexto (LER antes — C-04)
- services/api/app/domain/services/operations/canonical/counting_line.py (config_schema + validate_config + evaluate).
- A `config` é JSONB validada por op_class; o `state` já acumula count_in/count_out/prev_sides entre frames.

## Comportamento
- Config nova: `confirm_samples` (int, default 3, min 1) e `direction_debounce_frames` (int, default 5).
- `evaluate`: só conta um cruzamento quando o objeto manteve o novo lado da linha por `confirm_samples` frames
  consecutivos (voto majoritário), não no primeiro frame; aplicar debounce p/ não recontar reversões rápidas.
- `validate_config`: validar os novos campos (tipos/limites). Defaults preservam o comportamento atual se ausentes.
- Manter a aproximação por posição (best-effort) documentada — contagem fina segue edge/DeepSORT.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- services/api/app/domain/services/operations/canonical/counting_line.py
- services/api/tests/... (novos testes)

## Eval (default) — testes SÃO o critério
- cruzamento confirmado só após `confirm_samples` frames no novo lado (sequência sintética de detections).
- ruído de 1–2 frames NÃO conta; debounce evita dupla contagem em reversão rápida.
- defaults ausentes = comportamento anterior; validate_config rejeita valores inválidos.
- ruff + pytest verdes.

## Critérios de aceitação
- [ ] confirm_samples + debounce em evaluate; validate_config cobre os campos; testes verdes. PR para develop.

## Checkpoint
- Só PR (humano revisa — lógica de detecção, risk security). Sem produção. Sem migration.
