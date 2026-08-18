# D-060 · Reinícios: cada merge = DOIS deploys, e o guard do D-50 estava INATIVO

**Seção:** Rodada 4 — a caça ao congelamento (04/08, noite) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (evidência de deployment) · ✅ verificado · 📌 ação do Vitor**

Os 7 reinícios da noite (20:52→21:58) casam 1-a-1 com deployments (20–45 s após o `createdAt` de cada um;
zero FAILED/CRASHED — [[D-51]] confirmada). Refinamento novo: **cada merge dispara 2 deploys** — (a)
auto-deploy nativo do Railway (serviço API-V3 dev source-linkado ao branch develop, ~20 s após o push do
merge) e (b) `railway up` do workflow disparado por `workflow_run` do CI verde (~10 min depois). E o
concurrency guard do [[D-50]] **não estava valendo**: workflows `workflow_run` usam a definição do branch
DEFAULT (main), e `origin/main:railway-deploy-dev.yml` não tem o bloco `concurrency` (provado: runs
20:58:40 e 20:59:40 rodaram sobrepostos sem cancelamento). Mesmo ativo, o guard só serializa o caminho
CLI — o auto-deploy GitHub passa por fora. **Ação do Vitor:** desligar o auto-deploy do source-link no
serviço dev OU remover o `railway up` do CI; e portar o workflow corrigido (guard + fix do #304) para main.
