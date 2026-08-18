# D-051 · A cascata de supersessão de deploy — causa raiz PROVADA (substitui D-41)

**Seção:** 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · substitui [[D-41]]**

Evidência da plataforma (não dedução): dos 20 deployments recentes da API-V3, **19 estão `REMOVED` e 0
`CRASHED`/`FAILED`**. `REMOVED` = superado por um deploy mais novo; `CRASHED` = app caiu; `FAILED` =
build/healthcheck reprovou. Como não há **nenhum** CRASHED/FAILED, cada SIGTERM foi um deploy sendo
**superado por outro**, não crash nem healthcheck ruim nem OOM. O healthcheck é `/api/v1/health` (só toca
DB+Redis; `services/api/app/api/v1/health/routes.py:41-46`) e passou o tempo todo; `/readyz` = ready. O
intervalo consistente de ~5-7s é o *overlap de handover* (container novo fica healthy → o antigo recebe
SIGTERM), e os "dois containers ao mesmo tempo" são esse handover — não um loop de crash.

**Gatilho:** `.github/workflows/railway-deploy-dev.yml` roda `railway up` a cada CI verde no `develop`
(deploy commit-less por natureza — imagens `8c8bfc31`, `92ab19e4` sem SHA git). Um burst de merges (na
rodada, **3 PRs em 17 segundos**) vira um burst de `railway up`, cada um superando o anterior antes de
estabilizar. Some-se a isso deploys commit-less externos (`railway up` manual / variável sem
`--skip-deploys`) — o hazard já conhecido desta env.

**Por que a conclusão anterior falhou:** o "soak" que sustentou [[D-41]] usou `railway logs` em foreground
com redirect, que captura um **snapshot de ~22 segundos** e sai — o `sleep 900` seguinte só esperou sobre
um arquivo estático. Nunca observou a cascata. **Lição de método:** provar estabilidade por **uptime
contínuo** (`/livez` monotônico) e pelo **estado dos deployments** (REMOVED/CRASHED/FAILED), nunca por um
print de um instante nem por "health 200" (que passa durante a cascata).

Correção estrutural em [[D-50]]; disciplina operacional: mergear 1 PR por vez esperando SUCCESS, nunca
`railway up` casual na API, variáveis sempre `--skip-deploys`.
