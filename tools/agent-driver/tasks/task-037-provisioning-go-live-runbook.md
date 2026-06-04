---
title: "Provisionamento RVB + Plug-and-play day (Fase 8/10) — runbook on-site"
pr_title: "docs(edge): runbook de provisionamento RVB + dia do plug-and-play"
commit_message: "docs(edge): runbook Fase 8 (provisionamento RVB) + Fase 10 (plug-and-play day)"
eval: manual-hardware
budget_minutes: 90
risk: security
requires_hardware: true
status: BLOQUEADA-HARDWARE — execução on-site no dia do go-live. Fora da queue.txt autônoma.
---

# Tarefa 037 — Provisionamento RVB + Plug-and-play day (Fase 8/10) · BLOQUEADA-HARDWARE

> 🔴 Execução física na RVB. É majoritariamente **runbook + configs reais** (não código novo).

## Objetivo
Fechar o go-live: provisionar os dados reais da RVB (28 câmeras, 3 cenários — EPI/Qualidade/Counting,
enrollment tokens, MikroTik, modelos por módulo) e o checklist do dia em que o PC chega ao site (~30 min até processar).

## Depende de
- TUDO acima pronto: 029–035 (cloud+edge), modelos por módulo treinados, MikroTik (031/033).

## Escopo (runbook + seeds)
- Seeds/config reais: site RVB, 28 câmeras (RTSP/credenciais como segredo), 3 cenários desenhados (ROI/linha/zona),
  enrollment tokens, pin de modelo por módulo.
- Runbook day-of: ligar PC → install.sh → MikroTik conecta → enrollment → 3 pipelines processando → validar no painel.
- Critérios de aceite do go-live: 3 frentes no ar, eventos no cloud < 5s, painel mostrando, MikroTik dando acesso remoto.

## Eval (manual-hardware) / Critérios
- [ ] No site: 3 frentes funcionando juntas, validadas no painel; acesso remoto pelo MikroTik OK.

## Checkpoint
- HARDWARE + ON-SITE. Execução supervisionada; backup/rollback prontos.
