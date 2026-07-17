---
title: "Integração monofatura — esqueleto (inbound bipagem + outbound evidência por etapa)"
risk: security
adr: 0053
---

# Task 108 — Monofatura: esqueleto plugável (ADR-0053)

## Objetivo
- **Inbound:** endpoint "peça bipada" (ID da peça) → abre **sessão de inspeção** (idempotente por
  ID×etapa, tenant-scoped; migration aditiva se preciso, em commit separado).
- **Outbound:** ao fim de cada etapa, devolver **imagem de evidência + resultado (OK/falha por
  atributo) + tempo de etapa**, associado ao ID da peça.
- Contrato REAL = input do cliente (pendente) → **adaptador PLUGÁVEL** (interface + implementação
  simulada); simular no stress da task-111.

## Regras
- Multi-tenant: cross-tenant → 404 (C-01); sem fallback de tenant (ADR-0017).
- Envelope `success/error` de `app.core.responses`; SQL só em repositories (C-03).
- Migration forward-only, harness 2x, commit separado da lógica (C-02/C-08).

## Critérios de aceitação
- [ ] POST bipagem idempotente (mesmo ID×etapa não duplica sessão) + testes tenant/401/404.
- [ ] Interface outbound plugável com adaptador simulado + registro do payload por etapa.
- [ ] PR para develop (risk:security → revisão humana).
