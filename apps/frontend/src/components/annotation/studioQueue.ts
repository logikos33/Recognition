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
