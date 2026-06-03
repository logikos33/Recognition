---
title: "<título curto — vira título do PR>"
pr_title: "<opcional — sobrescreve title pro PR>"
commit_message: "feat(scope): <subject>"
eval: default   # ou: harness (ver checks em config.yaml)
---

# <Título da tarefa>

## Objetivo

<1–3 frases. O que esta tarefa entrega e por quê.>

## Arquivos no escopo

<Lista explícita dos arquivos que podem ser tocados. Driver NÃO bloqueia, mas o claude é instruído a respeitar.>

- `path/to/file1.py`
- `path/to/file2.md`

## Critérios de aceitação

- [ ] <Condição 1 verificável objetivamente>
- [ ] <Condição 2>
- [ ] Eval `<default|harness>` verde.
- [ ] Diff não toca paths protegidos (`infra/migrations/`, `.github/`, `railway_start.py`).

## Eval

`<default>` roda ruff + pytest + tsc.
`<harness>` roda `bash tests/harness/migrations/run.sh`.

Critério pass: todos os comandos exit 0.

## Checkpoints

- Único checkpoint: revisão humana da PR. Driver NUNCA mergeia.
- Sem banco de produção/staging tocado.
