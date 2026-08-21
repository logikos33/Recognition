/**
 * Fila do estúdio de boxes: o que é ANOTÁVEL, e nada além disso.
 *
 * Por que existe: a galeria é um NAVEGADOR — mostrar `duvida`, `excluida` e já
 * anotado ali é correto, é o ponto dela. O erro estava na ENTREGA: `openStudioAt`
 * repassava a página da galeria crua para o estúdio, e o anotador recebia de
 * volta o que já tinha julgado.
 *
 * Medido em 2026-08-18, requisição padrão da galeria (`page_size=60`, sem
 * filtro): dos 60 devolvidos, **35 eram `duvida` e 25 já anotados**. Soma 60 —
 * NENHUM era trabalho novo.
 */

/** Frame que ainda pede veredito humano. */
export function eAnotavel(f: {
  is_annotated?: boolean
  annotated?: boolean
  curation_status?: string | null
}): boolean {
  const anotado = f.is_annotated ?? f.annotated ?? false
  const curadoria = f.curation_status ?? 'active'
  return !anotado && curadoria === 'active'
}

/**
 * Filtra a lista que vai ao estúdio.
 *
 * ⚠️ Se o anotador abriu um frame ESPECÍFICO (clique num card já julgado), esse
 * frame é preservado mesmo fora do critério — ele pediu por aquele. O filtro
 * existe para a FILA, ⛔ não para censurar uma escolha explícita.
 */
export function filaDoEstudio<T extends { id: string; is_annotated?: boolean; curation_status?: string | null }>(
  frames: readonly T[],
  indiceEscolhido: number,
): { frames: T[]; initialIndex: number } {
  const escolhido = frames[indiceEscolhido]

  // Preserva a ORDEM da página. Hastear o escolhido para o topo mudaria a
  // sequência que o anotador está vendo — a fila mexer sob os olhos é pior que
  // fila mal ordenada (mesma lição do refill da tela irmã).
  const fila = frames.filter(f => eAnotavel(f) || f.id === escolhido?.id)
  const idx = escolhido ? fila.findIndex(f => f.id === escolhido.id) : 0
  return { frames: fila, initialIndex: Math.max(0, idx) }
}

/**
 * Reabastecimento da fila (relato de 21/08: a fila parava em 48 — a página de
 * 60 da galeria virava 48 anotáveis no `filaDoEstudio` e o estúdio NUNCA pedia
 * a página 2; com 2.809 pendentes, a revisão morria na primeira página).
 *
 * `true` quando restam poucos frames à frente e a fonte não está esgotada.
 * O limiar de 12 dá fôlego para a busca chegar antes de o anotador alcançar
 * o fim (ritmo medido de revisão: ~1 frame/2s; a página leva ~1-2s).
 */
export function precisaDeReabastecimento(
  index: number,
  tamanhoFila: number,
  esgotado: boolean,
): boolean {
  if (esgotado || tamanhoFila === 0) return false
  return tamanhoFila - index <= 12
}

/**
 * Anexa ao FIM, sem repetir id e sem reordenar o que já está na fila.
 *
 * Por que dedup: com `pending_review`, revisar um frame o REMOVE do filtro no
 * servidor — a paginação desliza (mesma família do OFFSET que perdia 50% no
 * #500). O refill re-busca a página 1 do filtro e confia neste dedup para
 * separar o que já está na fila local do que é trabalho novo.
 * ⚠️ Anexar ao fim, NUNCA reordenar: a fila mexer sob os olhos do anotador é
 * pior que fila mal ordenada (lição do #487).
 */
export function anexarSemRepetir<T extends { id: string }>(
  fila: readonly T[],
  novos: readonly T[],
): T[] {
  const vistos = new Set(fila.map(f => f.id))
  const ineditos = novos.filter(f => !vistos.has(f.id) && (vistos.add(f.id), true))
  return ineditos.length ? [...fila, ...ineditos] : [...fila]
}
