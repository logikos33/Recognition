# D-179 · Guard de split degenerado — implementado (executa D-165)

**Data:** 2026-08-18 · **Status:** ✅ vigente

[[D-165]] decidiu o aviso e registrou, com todas as letras, que **não tinha código**. Aqui tem.

**O que ficou.** `_diagnosticar_split()` roda logo depois de `_split_by_group` e devolve a lista de
avisos. Cada aviso vai para o log **e** para o `result` da task (`split_warnings`) — aviso que ninguém
lê é silêncio com passos extras.

| checagem | limiar | de onde veio o número |
|---|---|---|
| split abaixo do mínimo utilizável | **10 imagens** | *"precisão sobre n=2 não é medida, é ruído com casas decimais"* (#426) |
| proporção real longe da pedida | **15 pp** | os dois casos reais desviaram 17 pp (v3-treino1) e 16 pp (v4) |
| classe treina e **some** do test | zero | avaliação fica cega para ela — o veredito sai sem ela |
| classe com suporte fraco no test | **10 instâncias** | o test de 179 imagens tinha classes com 2, 6 e 7 |

⚠️ **Avisa, ⛔ não recusa.** [[D-165]] pede "aviso alto", e abortar o export puniria justamente o
dataset pequeno — que é a fase em que a causa se resolve sozinha (entra mais câmera, mais dia). Recusa
aqui bloquearia o flywheel que conserta o problema.

⛔ **O split por grupo NÃO mudou.** É ele que impede vazamento de câmera+dia, e é uma das coisas em que
batemos o benchmark ([[D-128]]). O que faltava era o aviso, e é só o aviso que entrou.

**Os dois casos reais viraram teste**, com os números medidos: 210/6/179 e 354/51/8. Limiar que não
pega o caso que motivou o guard é limiar decorativo.
