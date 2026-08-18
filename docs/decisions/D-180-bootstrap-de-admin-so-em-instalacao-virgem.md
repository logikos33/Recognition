# D-180 · Bootstrap de admin só em instalação virgem (executa D-166)

**Data:** 2026-08-18 · **Status:** ✅ vigente

[[D-166]] decidiu o gate e registrou, com todas as letras, que **não tinha código**. Aqui tem.

**A briga.** `railway_start.create_admin()` roda a **cada boot** e insere em `users` **sem
`tenant_id`**. A migration `046_deactivate_default_tenant.sql` (ADR-0017) desativa justamente os
usuários do tenant `default`, chamando-os de *"artefato de bootstrap sem dono ativo"*. Os dois rodam
em todo deploy, **um desfazendo o outro** — foi assim que `ADMIN_EMAIL` acabou apontando para conta
inativa em tenant errado ([[D-161]]).

**O gate.** `_instalacao_virgem()`: o bootstrap só roda quando **não existe nenhum tenant**. Banco sem
a tabela `tenants` conta como virgem — não há tenant que possa ser desfeito. Em DEV e em produção há
tenant, então ele não roda mais: some o lado da briga que era supérfluo, e a migration 046 passa a
ser a única voz.

⛔ **Nada removido, nada desativado.** O admin que já existe continua como está. O gate só impede a
**criação** repetida a cada deploy.

**Efeito colateral bom:** `railway_start.py` ganhou a guarda `if __name__ == '__main__'`. O Railway
sempre roda `python3 railway_start.py`, então produção não muda em nada — mas sem ela um
`import railway_start` **bootava um serviço**, e era por isso que nenhuma função deste arquivo tinha
teste. Agora tem.

**Descartado:** dar `tenant_id` ao INSERT do bootstrap. Escolher qual tenant é decisão de produto, e
o bootstrap existe para a instalação virgem — onde não há tenant a escolher.
