# ADR-0033 — Evidência: clipes de vídeo, duração configurável e retenção

**Status:** Aceita (2026-07-07) · **Estende:** ADR-0028/0027 (evidência cloud-first R2 + retenção),
migration 079_retention_days · **Relaciona:** ADR-0026 (config por câmera), verification-queue,
epi-alerts, counting.

## Contexto (pontos B2, B3, C4, C5, L14)

Hoje a evidência é só o **frame** do momento. Ao verificar um cenário (HITL) ou revisar um alerta/
contagem, o usuário precisa de **contexto de vídeo**, não uma foto isolada. E a contagem só mostra o
número de cruzamentos — sem acesso às evidências nem filtro de período.

## Decisão

- **Evidência = clipe de vídeo curto (~20-30s) ao redor do evento**, com **pré/pós configuráveis pelo
  admin** (ex.: 10s antes + 20s depois). Armazenado no **R2 por tenant/câmera** (ADR-0028), com
  **retenção configurável** (estende migration 079). O frame continua como thumbnail; o clipe é o
  contexto.
- **Duração e retenção configuráveis por tenant/admin:** janela do clipe, dias de retenção, e o que
  reter (por módulo/severidade). A tela de Retenção detalha **o que** está sendo retido, **onde** (R2,
  prefixo por tenant) e **por quanto tempo** (ponto L14).
- **Contagem (B2, B3):** cada cruzamento tem evidência (clipe) **selecionável** ao abrir; a tela tem
  **filtro de data/hora** pra buscar a contagem dentro do período.
- **Verificação EPI (C4):** ao verificar um cenário, trazer o **clipe do momento** (não só o frame) pra
  o revisor decidir com contexto.
- **Config (C5):** admin define a **duração** dos clipes e a **política de armazenamento/retenção** deles.

## Front (agora)
- Player de **clipe** (com controles) no alerta/verificação/contagem, além do frame.
- Config de duração/retenção do clipe no admin (Retenção).
- Contagem: lista de cruzamentos com evidência selecionável + filtro data/hora.
- Marcar "em breve" onde a captura de clipe no backend ainda não existe (o fluxo visual existe).

## Consequências
- Mais storage (clipe > frame) — por isso duração e retenção configuráveis; casa com o custo R2 (sem
  egress) e o ring buffer do edge (ADR-0028). Backend de captura de clipe = roadmap.
