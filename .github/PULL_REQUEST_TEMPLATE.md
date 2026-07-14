## O que muda
<!-- Resumo objetivo. Link da task (tools/agent-driver/tasks/task-NNN-*.md) e ADRs referenciadas. -->
- Task:
- ADR(s):
- Classificação de impacto: <!-- P0-CRÍTICO | P1-ALTO | P2-MÉDIO | P3-BAIXO -->

## Como testei (evidência obrigatória)
<!-- Cole a saída. Sem evidência, o PR não avança. -->
- [ ] Teste **falha-antes/passa-depois** (mostrar vermelho→verde)
- [ ] `pytest` (área afetada) verde
- [ ] `ruff check .` (se backend) / `npx tsc --noEmit` (se frontend)
- [ ] Migration: forward-only, **commit separado**, harness rodado **2x** (idempotência) — colar saída
- [ ] UI: **screenshots antes/depois**

## Disciplinas
- [ ] Nasceu em worktree de `origin/develop` (não `wip/*`)
- [ ] Multi-tenant: query filtra tenant; cross-tenant → 404 (C-01)
- [ ] Sem AGPL no caminho servido (detector ONNX Apache)
- [ ] Sem segredo commitado; sem f-string com input em SQL; sem `print()` no backend
- [ ] `risk:security` → security-review + **STOP-for-review** (não mergear sem gate humano)

## Registro
- [ ] Atualizei status da task, `docs/CHANGELOG.md` e (se schema) `docs/DATABASE.md`
- [ ] ADR/`DECISIONS.md` atualizados conforme a decisão

## Pós-merge
- [ ] Excluir branch (local+remota) e remover worktree · [ ] Equalizar ambientes se houve promoção
