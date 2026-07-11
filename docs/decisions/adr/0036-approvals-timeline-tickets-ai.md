# ADR-0036 — Aprovações com contexto/timeline + auditoria + tickets com IA generativa

**Status:** Aceita (2026-07-07) · **Relaciona:** admin-training-approvals, admin-audit-log,
admin-tickets, ADR-0031 (modelos), portal de serviços (futuro).

## Contexto (pontos J12, N15, O17)

Hoje a aprovação só mostra "aprovar/rejeitar" sem contexto — o super admin não sabe **o que** está
aprovando nem **por quê**. A auditoria lista ações sem detalhe. E os tickets não têm propósito claro.

## Decisão

### 1. Aprovações com contexto + timeline + comunicação (J12)
- Ao clicar num item de aprovação, abrir o **detalhe do que se aprova**. Ex.: para um **modelo** —
  classes que ele detecta, métricas (mAP/precision/recall por classe), **linhagem** (dataset→treino→
  modelo, ADR-0031), quem solicitou.
- **Timeline estilo ServiceNow:** histórico do item (criado → treinado → submetido → em análise →
  aprovado/rejeitado), com quem/quando em cada passo.
- **Campo de comunicação com o solicitante** (thread tipo ticket): o aprovador pede ajuste/explicação;
  o solicitante responde. Decisão com contexto e diálogo, não no escuro.

### 2. Auditoria com timeline por ação (N15)
- Cada ação no audit log abre um **detalhe/timeline**: quem, quando, o quê, **antes/depois** (diff),
  origem (IP/sessão). Não só uma linha.

### 3. Tickets com IA generativa (O17)
- Tela de tickets com um **balão de chat com IA generativa**: o usuário descreve o problema, a IA
  triа/abre o ticket, sugere solução. Futuramente integra com o **portal de serviços** da Logikos —
  aí os tickets ganham sentido pleno (fluxo de atendimento).
- **Desenhar agora** o chat com IA + a lista/detalhe de tickets, marcado **"em breve"** onde depende da
  IA/portal no backend.

## Front (agora)
- Aprovações: modal/drawer com detalhe do item + timeline + thread de comunicação.
- Auditoria: linha → detalhe/timeline com diff.
- Tickets: lista + detalhe + balão de IA generativa ("em breve").

## Consequências
- Aprovar com contexto reduz erro e dá rastreabilidade (governança). A timeline/diff exige o backend
  registrar histórico (audit trail). A IA de tickets e o portal são roadmap — o design mostra a visão.
