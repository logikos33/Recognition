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
