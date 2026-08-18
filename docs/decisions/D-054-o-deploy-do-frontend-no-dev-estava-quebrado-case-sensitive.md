# D-054 · O deploy do Frontend no dev estava quebrado (case-sensitive)

**Seção:** 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude (achado + fix) · ✅ vigente · PR #304**

`.github/workflows/railway-deploy-dev.yml` chamava `railway up --service "frontend"` (minúsculo), mas o
serviço é **"Frontend"**. Todo run do job `deploy-frontend` falhava com `Service not found` — o Frontend
**nunca deployava via CI**, só por deploy manual out-of-band (frágil, e fonte provável de deploys
commit-less que reiniciam a env). Achado ao investigar por que os runs do workflow apareciam como
`failure` (o `deploy-api` sempre passou). Fix: `frontend` → `Frontend`. Descoberto durante a verificação
do item 1 desta rodada.
