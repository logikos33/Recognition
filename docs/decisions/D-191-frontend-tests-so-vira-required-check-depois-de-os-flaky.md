# D-191 · Frontend tests só vira required check depois de os flaky morrerem

**Data:** 2026-09-02 · **Status:** ✅ vigente

Medido em 2026-09-02: a `develop` exige 3 checks (License gate · Migrations harness · Tests
pytest). **`Frontend tests (tsc + vitest + playwright)` não é required** — um frontend
vermelho não bloqueia merge hoje.

**Decisão:** promover `Frontend tests` a required check **só depois** de as famílias de
teste instável estarem mortas com prova (#618, #627, `Modulos.test.tsx`, e o e2e
`task-078-visual`). Até lá, fica não-required.

**Por quê:** required check só vale se for confiável. Promover um check que pisca
transforma cada PR legítimo em refém de um dado aleatório — e o time aprende a pedir
rerun, que é exatamente como um vermelho de verdade passa despercebido. A ordem
correta é fundação primeiro: conserta a causa, prova por mutação, só então tranca.

**Descartado:** promover agora e conviver com rerun (ensina a ignorar vermelho);
promover só o `tsc`/`vitest` sem o e2e (parte o check em dois e esconde o e2e do gate).

**Executada em 2026-09-05 (#681).** A condição foi cumprida: #654 (`mata duas famílias de
teste instável`) mergeado às 16:31. Os 5 required checks foram aplicados nas três branches
(`develop`, `staging`, `main`) e conferidos por `gh api .../required_status_checks`. Blast
radius medido antes de aplicar: os 11 PRs abertos no momento já reportavam `Frontend tests`
e `TypeScript check` **verdes** — nenhum ficou refém.
