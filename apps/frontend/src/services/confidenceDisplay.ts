/**
 * Confiança exibida ao cliente (contrato A1c) — a confiança crua da IA NÃO
 * prevê acerto, e mostrá-la como "97%"/"100%" faz o operador ler como
 * probabilidade de acerto quando não é.
 *
 * Medido no DEV (vereditos humanos reais, tenant RVB — não é estimativa):
 *   confiança exibida | n  | acertos | precisão REAL
 *   100%               | 36 | 21      | 58,3%
 *   99%                | 22 | 13      | 59,1%
 *   97–98%             | 17 | 11      | 64,7%
 *   95–96%             | 7  | 4       | 57,1%
 * A precisão é PLANA (~58–65%) em toda a faixa onde vivem quase todos os
 * alertas — "100% de confiança" acerta 58% das vezes. Mesma família do
 * "zero é uma afirmação" da casa (CLAUDE.md): agora é "100% é uma afirmação".
 *
 * Política única, uma função por papel — mesmo padrão de `nomeInternoOuCliente`
 * em `modelDisplay.ts` (superadmin = visão de engenharia, resto = visão do
 * produto):
 *   - superadmin: número cru, como sempre (`confiancaBruta`).
 *   - qualquer outro papel: NUNCA o número cru. Se houver precisão MEDIDA
 *     por classe (vereditos humanos, não a confiança da própria IA), linguagem
 *     leiga ancorada nela. Sem medição → diz isso, nunca inventa, nunca 0.
 *
 * PEDIDO-AO-BACKEND (ver contrato A1c, item 4): hoje NADA serve precisão
 * medida por classe — nenhum call site tem de onde tirar `precisaoMedida`, e
 * por isso todos caem no ramo "precisão ainda não medida". O parâmetro já
 * existe para o dia em que o backend servir isso (ex.: `alerts.precisao_classe`
 * vindo de um agregado sobre `verification_verdict`) — nenhum call site
 * precisará mudar de novo, só passar o valor.
 */
export function confiancaBruta(confidence: number | null | undefined): string {
  if (confidence == null) return '—'
  return `${Math.round(confidence * 100)}%`
}

/** Precisão medida (0..1) — não a confiança da própria IA — em linguagem leiga. */
export function confiancaHonesta(
  confidence: number | null | undefined,
  precisaoMedida?: number | null,
): string {
  if (confidence == null) return '—'
  if (precisaoMedida == null) return 'precisão ainda não medida'
  return `de cada 10 avisos assim, ~${Math.round(precisaoMedida * 10)} são reais`
}

/** Rótulo de confiança para QUALQUER superfície com texto/coluna/ficha
 * (tabela, painel, ficha de verificação): superadmin vê o número cru,
 * qualquer outro papel vê a leitura honesta. Todo novo lugar que mostra
 * confiança DEVE chamar esta função, nunca `Math.round(x.confidence*100)}%`
 * cru. */
export function confiancaInternaOuCliente(
  confidence: number | null | undefined,
  isSuperAdmin: boolean,
  precisaoMedida?: number | null,
): string {
  if (isSuperAdmin) return confiancaBruta(confidence)
  return confiancaHonesta(confidence, precisaoMedida)
}
