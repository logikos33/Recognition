---
title: "Qualidade: integração monofatura (webhook 'peça bipada' inbound + evidência/resultado outbound por etapa)"
pr_title: "feat(quality): integração bidirecional com a monofatura (trigger por código de barras + devolução de evidência)"
commit_message: "feat(quality): webhook de peça bipada + API de devolução de evidência por etapa"
eval: default
risk: security
requires_migration: talvez (sessão de inspeção + associação ao ID da peça)
depende_de: ADR-0048
bloco: RVB multi-módulo
---

# Task 108 — Integração monofatura (in/out)

## Objetivo
Fechar o loop da qualidade com o sistema de monofatura da RVB.

## Escopo
- **Inbound:** endpoint/webhook que recebe "peça bipada" (ID do código de barras) → abre **sessão de inspeção** da peça.
  Tenant/site-scoped, autenticado, idempotente (X-Batch-Id/ID da peça). Migration aditiva se precisar de tabela de sessão.
- **Outbound:** ao fim de cada etapa, **POST** de volta pra monofatura com **imagem de evidência** (ou clipe) + resultado
  (OK/falha por atributo) + tempo de ciclo, associado ao ID da peça.
- **Contrato da API = input do cliente** (a preencher): como eles chamam e o que devolver. Deixar o adaptador plugável.

## Aceite
- [ ] Bip de peça → sessão aberta no edge; ao fim de cada etapa → evidência+resultado devolvidos por API; idempotente; tenant-scoped (404 cross-tenant).

## Checkpoint
- STOP-for-review. Migration (se houver) separada da lógica. Contrato real da monofatura pendente do cliente.
