# Handoff de continuidade

> Estado vivo do projeto para quem retomar. **Sempre reconciliar com o real (`git fetch` fresco + `gh`), nunca
> confiar neste arquivo nem em memória** (C-04 / DIRETRIZ §6.1).

## Estado da `develop` — 2026-07-18 (pós-consolidação)

- **HEAD:** merge do #189 (`9f1e3f04` no momento da escrita — reconferir com `gh api .../branches/develop`).
- **Consolidação desta rodada:** mergeados **#197** (shootout Qualidade + housekeeping), **#194** (provisionamento
  edge), **#189** (4 P1 de segurança). Fechado **#112** (superseded). **#78** recomendado fechar (aguarda Vitor).
  Detalhe: `docs/CONSOLIDACAO_DEVELOP_2026-07-18.md`.
- **CI da develop:** substantivos verdes (License gate, ruff, tsc, Migrations harness, Frontend, SAST/SBOM);
  pytest completa em ~7min; única falha = `SCA (npm audit) (landing)` (ruído pré-existente) + gitleaks (bug conhecido).
- **Divergência:** `develop` **+119/−2 vs staging**, **+125/−3 vs main** (`docs/EQUALIZACAO_BRANCHES_2026-07-18.md`).

## 🔴 Bloqueios / decisões pendentes (Vitor)

1. **Senha `admin@rvb.com.br`** commitada no git → rotacionar **pela app** (nunca shell/SQL). **Bloqueante go-live.**
2. **AGPL em produção:** a `staging` ainda serve `from ultralytics import YOLO` (`quality_inference.py:272,552`);
   a develop já está limpa. Corrige-se na **promoção develop→staging** (gate humano).
3. **Colisão de migration `052`** na develop (6 arquivos, `run_migrations` chaveia por prefixo → 5 puladas em deploy
   fresh). Pré-existente; main já renumerou (#159) mas os slots colidem com 102-105 da develop → precisa de
   reconciliação deliberada. **Não forçado.** (CONSOLIDACAO §Achado 2.)
4. **Fan `quiet→cool`** antes da carga 24/7 (sudo, task-097).
5. **#78** — fechar como superseded ou apontar delta a extrair.
6. **Promoção `develop→staging`** — evento próprio (janela + rollback + smoke test). NÃO nesta rodada.

## Próximos passos técnicos (quando o Vitor liberar)

- Fechar o head-to-head do shootout de Qualidade: RT-DETRv4-S/M + RF-DETR budget-matched + nível C (engine TRT,
  parser DeepStream, stress 2×4MP no cenário ADR-0053). D-FINE-S já convergiu e bate o RF-DETR (AP_small 0.626).
- Reconciliar a numeração de migration develop↔main (colisão 052) num PR de migration próprio.
- Back-portar os hotfixes de CI staging/main→develop (`EQUALIZACAO §6`).

## Contexto vivo relacionado
`docs/CONSOLIDACAO_DEVELOP_2026-07-18.md` · `docs/HIGIENE_REPO_2026-07-18.md` · `docs/EQUALIZACAO_BRANCHES_2026-07-18.md`
· `docs/edge/SHOOTOUT_QUALIDADE_2026-07-18.md` · `docs/edge/SOAK_RVB_2026-07-18.md` · ADRs 0043/0044/0053.
