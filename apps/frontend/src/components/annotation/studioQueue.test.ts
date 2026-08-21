import { describe, expect, it } from 'vitest'

import { eAnotavel, filaDoEstudio } from './studioQueue'

const f = (id: string, extra: Record<string, unknown> = {}) => ({
  id, is_annotated: false, curation_status: 'active', ...extra,
})

describe('eAnotavel', () => {
  it('active e não anotado é anotável', () => {
    expect(eAnotavel(f('a'))).toBe(true)
  })

  it('⛔ já anotado NÃO volta para a fila', () => {
    expect(eAnotavel(f('a', { is_annotated: true }))).toBe(false)
  })

  it('⛔ duvida e excluida NÃO voltam para a fila', () => {
    expect(eAnotavel(f('a', { curation_status: 'duvida' }))).toBe(false)
    expect(eAnotavel(f('a', { curation_status: 'excluida' }))).toBe(false)
  })

  it('sem os campos, assume anotável — não some trabalho por omissão', () => {
    expect(eAnotavel({ id: 'a' } as never)).toBe(true)
  })
})

describe('filaDoEstudio', () => {
  it('🔴 o caso medido em campo: 60 devolvidos, nenhum anotável', () => {
    const pagina = [
      ...Array.from({ length: 35 }, (_, i) => f(`d${i}`, { curation_status: 'duvida' })),
      ...Array.from({ length: 25 }, (_, i) => f(`a${i}`, { is_annotated: true })),
    ]
    expect(filaDoEstudio(pagina, 0).frames.filter(eAnotavel)).toHaveLength(0)
  })

  it('mantém só os anotáveis e preserva a posição do escolhido', () => {
    const pagina = [f('x', { is_annotated: true }), f('b'), f('c')]
    const r = filaDoEstudio(pagina, 1)  // clicou no 'b'
    expect(r.frames.map(x => x.id)).toEqual(['b', 'c'])
    expect(r.frames[r.initialIndex].id).toBe('b')
  })

  it('⚠️ clique EXPLÍCITO num já-julgado é respeitado — não se censura escolha', () => {
    const pagina = [f('b'), f('julgado', { curation_status: 'duvida' }), f('c')]
    const r = filaDoEstudio(pagina, 1)
    expect(r.frames[r.initialIndex].id).toBe('julgado')
    expect(r.frames.map(x => x.id)).toEqual(['b', 'julgado', 'c'])  // ORDEM preservada
  })
})

// ── reabastecimento da fila (bug de 21/08: revisão parava nos 48 da 1ª página) ──
import { anexarSemRepetir, precisaDeReabastecimento } from './studioQueue'

describe('precisaDeReabastecimento', () => {
  it('pede mais quando restam <=12 à frente — é o que o defeito NÃO fazia', () => {
    // Regressão do relato: fila de 48 (página de 60 filtrada), 2.809 pendentes.
    // Sem o refill, o anotador em 47/48 morria ali. Este assert falha na
    // versão antiga por construção: nada pedia a próxima página.
    expect(precisaDeReabastecimento(40, 48, false)).toBe(true)
    expect(precisaDeReabastecimento(47, 48, false)).toBe(true)
  })
  it('não pede no meio da fila, com fonte esgotada, nem com fila vazia', () => {
    expect(precisaDeReabastecimento(10, 48, false)).toBe(false)
    expect(precisaDeReabastecimento(47, 48, true)).toBe(false)
    expect(precisaDeReabastecimento(0, 0, false)).toBe(false)
  })
})

describe('anexarSemRepetir', () => {
  const f = (id: string) => ({ id })
  it('anexa ao fim sem duplicar e sem reordenar (lições #487/#500)', () => {
    const fila = [f('a'), f('b'), f('c')]
    // A página re-buscada desliza (pending_review remove revisados no
    // servidor): vem mistura de já-na-fila + novos. Só o novo entra.
    const r = anexarSemRepetir(fila, [f('b'), f('d'), f('e'), f('d')])
    expect(r.map(x => x.id)).toEqual(['a', 'b', 'c', 'd', 'e'])
  })
  it('página toda repetida = zero inéditos (é o sinal de avançar o cursor)', () => {
    const fila = [f('a'), f('b')]
    expect(anexarSemRepetir(fila, [f('a'), f('b')]).map(x => x.id)).toEqual(['a', 'b'])
  })
  it('fluxo do defeito: consumir 48 e continuar até 108 sem repetir frame', () => {
    let fila = Array.from({ length: 48 }, (_, i) => f(`p1-${i}`))
    // anotador chega ao fim da 1ª página → refill traz a página seguinte
    expect(precisaDeReabastecimento(40, fila.length, false)).toBe(true)
    fila = anexarSemRepetir(fila, Array.from({ length: 60 }, (_, i) => f(`p2-${i}`)))
    expect(fila.length).toBe(108)
    expect(new Set(fila.map(x => x.id)).size).toBe(108)  // nenhum repetido
    expect(fila[0].id).toBe('p1-0')  // ordem original intacta
  })
})
