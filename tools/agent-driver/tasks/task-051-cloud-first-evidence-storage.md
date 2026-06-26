---
title: "Storage de evidência cloud-first (R2) + buffer local limitado no edge"
pr_title: "feat(edge): evidência sempre em R2 + ring buffer local limitado"
commit_message: "feat(edge): upload de evidência pra R2 com buffer local por tamanho/idade"
eval: mixed (unit + manual-hardware)
budget_minutes: 90
risk: security
requires_hardware: parcial
status: código pode ser escrito/testado agora; validação de pressão de disco é on-site
---

# Tarefa 051 — Evidência cloud-first + buffer local limitado

## Problema
O Orin NX tem disco pequeno (128GB de fábrica + NVMe adicionado). Se a evidência (frames/clipes de
detecção) ficar acumulada localmente, **enche o disco e derruba o edge**. O `edge-sync-agent` hoje só
buferiza **eventos de detecção (JSON)** em SQLite com `purge_old(7d)` — **não há caminho gerenciado
para as IMAGENS/CLIPES**. Esta task fecha isso.

## Objetivo
Toda evidência sobe pra **Cloudflare R2** por tenant, com retenção definida na nuvem (task-047 /
migration 079_retention_days). O disco do edge é apenas **buffer transitório limitado** — nunca o
armazenamento de longo prazo.

## Escopo
### Edge (`services/edge-sync-agent`)
- Caminho de evidência: ao gerar frame/clipe de detecção, gravar em diretório de buffer no **NVMe**
  (não no disco do OS) e enfileirar upload pra R2 (presigned URL emitida pelo cloud, ou via endpoint
  cloud) — **streaming/multipart**, com a mesma resiliência do uploader de eventos (backoff, idempotência por hash).
- **Ring buffer limitado:** teto por **tamanho** (ex.: X GB) **e** idade (ex.: Y horas). Ao online,
  esvazia pra R2 e apaga local após confirmação. Offline, ao atingir o teto, **descarta o mais antigo**
  (registrar contagem de descartes — é métrica de saúde do link). Nunca crescer ilimitado.
- Métrica/heartbeat: uso do buffer (%, GB, itens pendentes, descartados) reportado ao cloud.

### Cloud (`services/api`)
- Confirmar prefixo R2 por tenant/câmera e que a retenção (task-047) expira por tier.
- Endpoint para presigned upload (se ainda não existir) com authz por device token + tenant derivado do token.

## Critérios de aceite
- Disco do edge **estável** sob detecção contínua (não cresce além do teto) — comprovar em bench.
- Evidência aparece em R2 no prefixo do tenant correto; nada cross-tenant.
- Offline prolongado: buffer respeita o teto, descarta o mais antigo, reconcilia ao voltar; descartes logados.
- Retenção cloud (task-047) expira no prazo do tier do tenant.
- Testes unitários do ring buffer (limite por tamanho/idade, descarte FIFO) + upload idempotente.

## Risco
security — caminho de upload + isolamento por tenant (token-derived) + deleção local. Review C2.
