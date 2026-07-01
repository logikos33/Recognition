# ADR-0027 — Evidência cloud-first (R2) + buffer local limitado no edge

**Status:** Aceito · **Data:** 2026-06-24 · **Relacionados:** ADR-0022 (mensageria), ADR-0025
(hardware), task-047 (retenção), task-051 (implementação), migration 079_retention_days.

## Contexto
O Orin NX tem disco pequeno. Se a evidência (frames/clipes) ficar acumulada no device, enche o disco
e **trava (intertravamento)**. O edge-sync-agent hoje buferiza só EVENTOS (JSON) com purge de 7 dias
— não há caminho gerenciado para as IMAGENS/CLIPES.

## Decisão
- **Toda evidência sobe para o Cloudflare R2** por tenant, com retenção configurável na nuvem
  (task-047 / migration 079). O disco do edge é apenas **buffer transitório limitado**.
- **RESTRIÇÃO DE DISCO (cravada):** o Orin NX tem **128GB de SSD = SO + aplicação. NÃO é destino de
  armazenamento.** Evidência/dados NÃO ficam no device — vão pro R2. Buffer transitório só até o teto
  configurado, preferencialmente no NVMe adicional (ADR-0025), NUNCA na partição do SO.
- **Margem livre reservada (anti-travamento):** manter SEMPRE ≥ X GB / ≥ Y% de disco livre,
  intocável. Um watchdog para de gravar / faz eviction do mais antigo ANTES de tocar essa reserva.
  Disco cheio = intertravamento — a reserva impede isso por design.
- **R2 + edge preparados pra receber o fluxo** (prefixo por tenant/câmera, retenção por tier) pra o
  local NUNCA precisar acumular. Upload via presigned URL, authz por device token RS256, tenant
  derivado do token (não do payload). R2 escolhido por não ter taxa de egress.
- **Ring buffer:** teto por tamanho E idade; online esvazia pra R2 e apaga local após confirmação;
  offline descarta o mais antigo ao atingir o teto (registrar contagem = saúde do link).

## Consequências
- Disco do edge **nunca enche** (reserva + ring buffer); retenção de longo prazo é da nuvem
  (custo previsível, ADR-0022/custo_rvb.xlsx).
- Perda controlada em offline prolongado (descarta o mais antigo) — aceitável e auditável.
- Isolamento por tenant no caminho de upload = item de review de segurança (C2).
- Implementação: task-051 (cloud-first evidence storage) — recriar se ausente do tree.
- Aceitação por device: a margem livre reservada é critério do EDGE_HARDWARE_ACCEPTANCE.md.
