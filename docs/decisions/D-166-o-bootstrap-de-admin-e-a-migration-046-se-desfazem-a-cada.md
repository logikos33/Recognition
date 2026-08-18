# D-166 · O bootstrap de admin e a migration 046 se desfazem a cada deploy

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

`railway_start.py:90-106` cria um admin **a cada boot**, com `INSERT INTO users` **sem `tenant_id`**.
A migration `046_deactivate_default_tenant.sql` (ADR-0017) **desativa** os usuários do tenant `default`,
chamando-os de *"artefato de bootstrap sem dono ativo"*. **Os dois rodam a cada deploy, um desfazendo o
outro** — foi isso que deixou `ADMIN_EMAIL` apontando para conta inativa em tenant errado (D-161).

**PROPOSTO — ⛔ SEM CÓDIGO NESTA RODADA:** o bootstrap deve rodar só se **não existir nenhum tenant** —
isto é, só na instalação virgem, que é o caso para o qual foi escrito. ⚠️ **A redação anterior dizia
"Consertado" e estava ERRADA.** Corrigido aqui.

**Verificado:** tenant `default` tem 0 câmeras, 0 frames, 0 anotações e 2 usuários inativos.
⛔ Nenhum dado do RVB vazou para lá. ⛔ Nada removido.
