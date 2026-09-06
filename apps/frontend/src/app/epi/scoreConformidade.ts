/**
 * O score de conformidade IMPRESSO — issue #789, para as DUAS telas que o
 * mostram.
 *
 * O número é `100 × (1 − horas-câmera com violação ÷ (câmeras ativas × horas))`
 * — a mesma fórmula no cartão do Dashboard (`module_service.get_stats`,
 * ADR-0065) e no relatório (`compliance_report_service._aggregate`, issue
 * #797). O denominador é enorme: 17 câmeras × 24 h = 408 horas-câmera/dia, e
 * × 168 h = 2.856 numa semana. Com isso UMA hora-câmera com violação vale
 * 0,245 % no dia e 0,035 % na semana — e `Math.round` levava qualquer taxa
 * ≥ 99,5 para o inteiro **100**.
 *
 * Medido no acervo do DEV: 25/08 teve 66 violações de EPI em 1 hora-câmera →
 * taxa 99,8 → a tela imprimia **100**, em verde, no dia mais violento do mês.
 * Na semana o efeito é maior ainda: até 14 horas-câmera com violação ainda
 * ficam ≥ 99,5.
 *
 * `100` passa a ser reservado ao 100 exato — o único valor em que
 * `horas com violação = 0`. Todo o resto desce para o inteiro abaixo: 99,8 e
 * 99,5 imprimem **99**, e 99 na tela é a diferença entre "não houve nada" e
 * "houve, e é pouco em cima de um denominador enorme".
 *
 * ⚠️ Vive num módulo próprio porque o mesmo número aparece em `Dashboard.tsx`
 * (cartão) e em `Relatorios.tsx` (resumo do período, o que vira PDF no R2 como
 * prova de auditoria). A primeira versão do conserto arrumou só o Dashboard, e
 * a mesma semana saía "99" numa tela e "100" na outra.
 *
 * Isto NÃO conserta o denominador (issue #823): 92 num dia de 152 violações
 * continua vindo do backend. O que este arredondamento garante é que nenhuma
 * das duas telas AFIRME perfeição sobre um período que teve violação.
 */
export function scoreImpresso(score: number): number {
  return score >= 100 ? 100 : Math.min(99, Math.floor(score))
}
