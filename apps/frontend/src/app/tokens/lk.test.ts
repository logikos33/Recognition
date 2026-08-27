/**
 * Os tokens são o contrato. Este teste guarda as regras que uma paleta
 * sozinha não consegue expressar.
 */
import { describe, expect, it } from 'vitest'

import { lk } from './lk.css'

describe('tokens Logikos', () => {
  it('expõe as três vozes tipográficas, e só três', () => {
    expect(Object.keys(lk.fonte).sort()).toEqual(['mono', 'titulo', 'ui'])
  })

  it('as medidas do shell são as do handoff', () => {
    // Números do README — mudá-los é decisão de design, não de implementação.
    expect(lk.medida.topbar).toBeTruthy()
    expect(lk.medida.sidebar).toBeTruthy()
    expect(lk.medida.sidebarColapsada).toBeTruthy()
  })

  it('estado tem os três, e nenhum a mais', () => {
    expect(Object.keys(lk.estado).sort()).toEqual(['atencao', 'nc', 'ok'])
  })

  it('ciano e magenta são tokens distintos — não se substituem', () => {
    expect(lk.cor.cianoVisao).not.toBe(lk.cor.magentaGlitch)
  })
})
