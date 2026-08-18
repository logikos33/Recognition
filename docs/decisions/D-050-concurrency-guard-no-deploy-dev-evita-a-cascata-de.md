# D-050 · Concurrency guard no deploy dev — evita a cascata de supersessão

**Seção:** 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · PR #300**

Correção estrutural da cascata de [[D-51]]. `concurrency: { group: railway-deploy-dev, cancel-in-progress:
true }` no nível do workflow `railway-deploy-dev.yml`: um burst de merges **colapsa num único deploy final**
(o mais recente vence; os anteriores em fila são cancelados antes de invocar `railway up`). Group **fixo**
(não por sha) para serializar todos os deploys da env; group no **nível do workflow** para manter a
atomicidade api+frontend (acoplados via `needs`), evitando "api novo + frontend velho". Verificado que
`railway up` é o único caminho de deploy da API nesta env (sem integração git nativa; `meta.source=None`).
