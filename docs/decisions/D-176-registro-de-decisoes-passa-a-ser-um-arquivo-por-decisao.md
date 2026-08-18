# D-176 · Registro de decisões passa a ser um arquivo por decisão

**Data:** 2026-08-18 · **Status:** ✅ vigente

**Problema medido, não suposto.** `docs/REGISTRO_DE_DECISOES.md` era um único arquivo append-only de
~3.580 linhas. Duas sessões em paralelo escrevem sempre na **mesma região do mesmo arquivo**: 3 colisões
de número `D-` em 3 rodadas. A prova está no próprio conteúdo — D-105 e D-106 tiveram de ser renumerados
para D-114 e D-115 na consolidação do merge #384, porque os números já estavam em uso na `develop`.

**Decisão.** Uma decisão, um arquivo: `docs/decisions/D-NNN-slug.md`, como as ADRs já eram.
`docs/decisions/INDICE.md` é **gerado**, nunca editado à mão.

**O que isso resolve — e o que não resolve.** Não impede duas sessões de escolherem D-176 ao mesmo tempo.
Troca o **custo** da colisão: em vez de resolver conflito de merge no meio de um arquivo gigante, o git
mostra dois arquivos adicionados e a resolução é `git mv` + regerar o índice.

**Migração por script, zero edição manual em massa.** `tools/decisoes.py split` copiou as 170 entradas
`### D-NN ·` com **corpo verbatim** (verificado: os 170 corpos aparecem literalmente no monólito).

**O monólito não foi apagado.** Continua íntegro e congelado. A regra append-only dele proibia apagar
entrada, e nenhuma foi apagada. O que não era entrada `D-` (constatações, notas de método) permanece
lá e só lá — não foi inventado arquivo para conteúdo que não era decisão.

**Gate.** `scripts/ci/check_docs_gate.py` ganhou a regra 7: número duplicado, título interno divergindo
do nome do arquivo, ou `INDICE.md` desatualizado **falham o CI**. Provado falhando antes e passando
depois. Sem gate, a convenção é decoração.

**Descartado:** manter o arquivo único e "combinar" reserva de números entre sessões — combinado já era
a regra, e colidiu 3 vezes.
