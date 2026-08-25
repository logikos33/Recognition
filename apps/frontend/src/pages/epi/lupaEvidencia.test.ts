/**
 * Limites da lupa. Os números vêm de simulação (50k eventos, palco 800x600):
 * ao aproximar a âncora é exata; ao afastar o reenquadramento vence a âncora.
 */
import { describe, expect, it } from 'vitest'
import {
  proximoEstado, limitePan, distanciaEntre,
  LUPA_INICIAL, ESCALA_MIN, ESCALA_MAX,
  type EstadoLupa,
} from './lupaEvidencia'

const PALCO = { largura: 800, altura: 600 }

describe('lupa da evidência — escala', () => {
  it('não passa do piso: afastar no 1x não gera escala < 1 e recentra', () => {
    const e = proximoEstado({ escala: 2, x: 399, y: -299 },
      { tipo: 'zoom', fator: 0.1, ancoraX: 100, ancoraY: 100 }, PALCO)
    expect(e.escala).toBe(ESCALA_MIN)
    expect(e.x).toBe(0)
    expect(e.y).toBe(0)
  })

  it('não passa do teto', () => {
    const e = proximoEstado({ escala: 7, x: 0, y: 0 },
      { tipo: 'zoom', fator: 100, ancoraX: 0, ancoraY: 0 }, PALCO)
    expect(e.escala).toBe(ESCALA_MAX)
  })

  it('zoom sem efeito devolve o MESMO objeto (não re-renderiza)', () => {
    const estado: EstadoLupa = { escala: ESCALA_MAX, x: 10, y: 10 }
    expect(proximoEstado(estado, { tipo: 'zoom', fator: 2, ancoraX: 0, ancoraY: 0 }, PALCO))
      .toBe(estado)
  })
})

describe('lupa da evidência — âncora', () => {
  it('aproximar mantém sob o cursor o mesmo pixel do frame', () => {
    // 2x ancorado 200px à direita do centro: x = 200 - 2*(200-0) = -200
    expect(proximoEstado(LUPA_INICIAL,
      { tipo: 'zoom', fator: 2, ancoraX: 200, ancoraY: 0 }, PALCO))
      .toEqual({ escala: 2, x: -200, y: 0 })
  })

  it('a âncora é EXATA ao aproximar, mesmo já deslocado', () => {
    const antes: EstadoLupa = { escala: 2, x: 120, y: -80 }
    const ancora = { x: 250, y: -110 }
    // ponto do conteúdo sob o cursor, em unidades de conteúdo
    const c = { x: (ancora.x - antes.x) / antes.escala, y: (ancora.y - antes.y) / antes.escala }
    const d = proximoEstado(antes, { tipo: 'zoom', fator: 1.15, ancoraX: ancora.x, ancoraY: ancora.y }, PALCO)
    expect(d.x + d.escala * c.x).toBeCloseTo(ancora.x, 9)
    expect(d.y + d.escala * c.y).toBeCloseTo(ancora.y, 9)
  })

  it('ao AFASTAR o reenquadramento vence a âncora (senão abriria faixa vazia)', () => {
    // no limite a 2x (x=400), afastando para 1.5x o limite cai para 200
    expect(limitePan(1.5, PALCO.largura)).toBe(200)
    const e = proximoEstado({ escala: 2, x: 400, y: 0 },
      { tipo: 'zoom', fator: 0.75, ancoraX: 400, ancoraY: 0 }, PALCO)
    expect(e).toEqual({ escala: 1.5, x: 200, y: 0 })
  })
})

describe('lupa da evidência — pan não deixa a imagem sumir', () => {
  it('arrastar além do limite para na borda, sem faixa vazia', () => {
    // limite a 2x = 800*(2-1)/2 = 400 e 600*(2-1)/2 = 300
    expect(proximoEstado({ escala: 2, x: 0, y: 0 },
      { tipo: 'arrastar', dx: 10000, dy: 10000 }, PALCO))
      .toEqual({ escala: 2, x: 400, y: 300 })
    expect(proximoEstado({ escala: 2, x: 0, y: 0 },
      { tipo: 'arrastar', dx: -10000, dy: -10000 }, PALCO))
      .toEqual({ escala: 2, x: -400, y: -300 })
  })

  it('em 1x não há o que deslocar: o pan fica zerado', () => {
    expect(limitePan(ESCALA_MIN, PALCO.largura)).toBe(0)
    expect(proximoEstado(LUPA_INICIAL, { tipo: 'arrastar', dx: 500, dy: 500 }, PALCO))
      .toEqual(LUPA_INICIAL)
  })

  it('palco sem medida (antes do layout) não gera pan', () => {
    expect(proximoEstado({ escala: 4, x: 0, y: 0 },
      { tipo: 'arrastar', dx: 50, dy: 50 }, { largura: 0, altura: 0 }))
      .toEqual({ escala: 4, x: 0, y: 0 })
  })

  it('reset volta ao enquadramento inteiro', () => {
    expect(proximoEstado({ escala: 6, x: -1200, y: 900 }, { tipo: 'reset' }, PALCO))
      .toEqual(LUPA_INICIAL)
  })
})

describe('pinça', () => {
  it('distância entre os dois dedos', () => {
    expect(distanciaEntre([{ x: 0, y: 0 }, { x: 3, y: 4 }])).toBe(5)
    expect(distanciaEntre([{ x: 0, y: 0 }])).toBe(0)  // um dedo só: não é pinça
  })
})
