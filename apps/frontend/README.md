
## Antes de empurrar: `npm run verificar`

Roda o que o CI roda, na mesma ordem: `tsc --noEmit`, os testes de unidade e os
de navegador.

**Por que existe:** `npm run test` (vitest) **não roda os specs de Playwright** —
`vitest.config.ts` exclui `src/test/e2e/**`. Rodar só ele e ver verde diz muito
menos do que parece. Em 29/08 isso enganou duas vezes na mesma tarde: 887 testes
verdes no laptop e vermelho no CI, uma vez por manifesto desatualizado e outra
por um bug que só os testes de navegador pegavam (o shell inteiro caía quando a
lista de tenants vinha sem a lista).
