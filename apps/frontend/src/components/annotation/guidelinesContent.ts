/**
 * Diretrizes de anotação — conteúdo estático versionado (tecla G no estúdio).
 *
 * O maior destruidor de dataset não é falta de imagem — é critério
 * inconsistente. Anotar a pessoa inteira em 200 frames e só a cabeça em 300
 * produz um modelo confuso, e não dá para corrigir sem reanotar tudo.
 *
 * Documento vivo: ao mudar o critério, atualize versão e data — e reanote o
 * que conflitar com a regra nova.
 */

export const GUIDELINES_VERSION = 'v1.0'
export const GUIDELINES_DATE = '2026-08-10'

export interface GuidelineSection {
  title: string
  items: string[]
}

export const GUIDELINES: GuidelineSection[] = [
  {
    title: 'Regra geral — o que é uma caixa',
    items: [
      'Uma caixa por objeto: aperte a caixa no objeto, sem folga além de ~2 px.',
      'Marque o EQUIPAMENTO, não a pessoa: a caixa de "capacete" cobre só o capacete, não a cabeça inteira.',
      'Objeto parcialmente visível ainda é objeto: marque a parte visível.',
      'Se você não consegue afirmar o que é, NÃO chute — tecle F (em dúvida) e siga.',
    ],
  },
  {
    title: 'Por classe (módulo EPI)',
    items: [
      'Capacete: casco do capacete, com aba. Boné/touca NÃO é capacete — não marque.',
      'Óculos: armação + lentes, na região dos olhos. Óculos no bolso ou na testa não contam como "em uso" — marque apenas se a operação pedir presença do objeto, não uso correto.',
      'Luva: cada mão com luva é UMA caixa (duas mãos = duas caixas).',
      'Colete: tronco coberto pelo colete refletivo. Se o colete está aberto, marque a área visível do colete.',
    ],
  },
  {
    title: 'Casos de borda',
    items: [
      'Pessoa cortada na borda do quadro: marque o EPI se pelo menos metade dele está visível; menos que isso, ignore.',
      'Objeto ocluído (atrás de máquina, caixa, outra pessoa): marque só a extensão VISÍVEL — a caixa não inclui a parte escondida.',
      'Longe demais para julgar (objeto < ~10 px): não marque e tecle F — imagem em dúvida vale mais que chute.',
      'Várias pessoas na cena: uma caixa por objeto de cada pessoa. Não agrupe.',
      'Reflexo em vidro, monitor ou poça: NUNCA marque reflexo.',
      'Imagem escura: use B (brilho/contraste) antes de decidir — o ajuste é só na exibição, o arquivo não muda.',
    ],
  },
  {
    title: 'Consistência',
    items: [
      'O critério desta página vale para TODAS as imagens — não mude no meio da sessão.',
      'Apareceu um caso que a diretriz não cobre? Tecle F, termine a sessão e registre o caso para a próxima versão deste documento.',
    ],
  },
]
