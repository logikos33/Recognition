---
title: "<título curto — vira título do PR>"
pr_title: "<opcional — sobrescreve title pro PR>"
commit_message: "feat(scope): <subject>"
eval: default   # ou: harness (ver checks em config.yaml)
risk: low       # low | security — ausência = security (fail-safe, NUNCA auto-merge)
---

# <Título da tarefa>

## NEEDS CLARIFICATION

> Listar aqui qualquer ambiguidade que bloqueia a implementação antes de começar (M1).
> Se não houver, escrever "Nenhuma." e remover esta instrução.
> Exemplos: "A coluna X existe no schema atual?", "O endpoint Y já está implementado?"

Nenhuma.

## Objetivo

<1–3 frases. O que esta tarefa entrega e por quê.>

## Critérios de aceitação

> Definir ANTES de qualquer código (M3 — test-first). Cada item deve ser verificável
> objetivamente sem ambiguidade.

- [ ] <Condição 1 verificável objetivamente>
- [ ] <Condição 2>
- [ ] Eval `<default|harness>` verde.
- [ ] Diff não toca paths protegidos (`infra/migrations/`, `.github/`, `railway_start.py`).

## Invariantes de segurança

> Se a tarefa tiver risco de segurança, listar as propriedades que NÃO podem ser violadas.
> Se risk: low, escrever "N/A (risk: low)".

- N/A (risk: low)

## Arquivos no escopo

<Lista explícita dos arquivos que podem ser tocados. Driver NÃO bloqueia, mas o claude é instruído a respeitar.>

- `path/to/file1.py`
- `path/to/file2.md`

## Eval

`<default>` roda ruff + pytest + tsc.
`<harness>` roda `bash tests/harness/migrations/run.sh`.

Critério pass: todos os comandos exit 0.

## Checkpoints

- Único checkpoint: revisão humana da PR. Driver NUNCA mergeia (L1).
- `risk: low` → queue_runner pode auto-mergear após CI verde + base develop.
- `risk: security` → queue_runner PARA e aguarda revisão humana antes de continuar o lote.
- Sem banco de produção/staging tocado.

---

## Convenção de risco (`risk`)

| Valor | Quando usar |
|-------|-------------|
| `security` | Toca auth, multi-tenant, tokens, migrations, dados de cliente, ou qualquer invariante de segurança. **Default quando o campo estiver ausente.** |
| `low` | Leitura pura, docs, display/frontend sem nova lógica de autenticação, utilitários sem acesso a dados sensíveis. |

> **Regra de ouro:** em caso de dúvida, use `security`. O custo de uma revisão humana extra é
> menor que o risco de um auto-merge inadequado.
