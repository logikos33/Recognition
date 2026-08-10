/**
 * Tests: geometria pura das caixas (desenhar / mover / redimensionar).
 */
import { describe, expect, it } from 'vitest'
import {
  boxFromDrag,
  MIN_BOX_SIZE,
  moveBox,
  resizeBox,
} from '../../../components/annotation/boxGeometry'
import type { Box } from '../../../components/annotation/studioTypes'

const base: Box = {
  id: 'b1',
  classId: 1,
  xCenter: 0.5,
  yCenter: 0.5,
  width: 0.2,
  height: 0.2,
}

describe('boxFromDrag', () => {
  it('cria caixa normalizada a partir de dois cantos (qualquer direção)', () => {
    const b = boxFromDrag(0.6, 0.6, 0.2, 0.3, 7, 'id')
    expect(b?.classId).toBe(7)
    expect(b?.xCenter).toBeCloseTo(0.4)
    expect(b?.yCenter).toBeCloseTo(0.45)
    expect(b?.width).toBeCloseTo(0.4)
    expect(b?.height).toBeCloseTo(0.3)
  })

  it('clique acidental (menor que o mínimo) não vira caixa', () => {
    expect(boxFromDrag(0.5, 0.5, 0.5 + MIN_BOX_SIZE / 2, 0.9, 1, 'id')).toBeNull()
  })
})

describe('moveBox', () => {
  it('move o centro e mantém a caixa inteira dentro da imagem', () => {
    expect(moveBox(base, 0.05, 0.5).xCenter).toBeCloseTo(0.1) // clampa em width/2
    expect(moveBox(base, 0.99, 0.5).xCenter).toBeCloseTo(0.9)
    expect(moveBox(base, 0.3, 0.3)).toMatchObject({ xCenter: 0.3, yCenter: 0.3 })
  })
})

describe('resizeBox', () => {
  it('alça leste move só a borda direita', () => {
    const r = resizeBox(base, 'e', 0.9, 0.5)
    expect(r.width).toBeCloseTo(0.5)
    expect(r.xCenter).toBeCloseTo(0.65)
    expect(r.height).toBeCloseTo(0.2)
  })

  it('alça noroeste move as bordas esquerda e superior', () => {
    const r = resizeBox(base, 'nw', 0.3, 0.3)
    expect(r.width).toBeCloseTo(0.3)
    expect(r.height).toBeCloseTo(0.3)
    expect(r.xCenter).toBeCloseTo(0.45)
    expect(r.yCenter).toBeCloseTo(0.45)
  })

  it('nunca inverte nem encolhe abaixo do mínimo', () => {
    const r = resizeBox(base, 'e', 0.0, 0.5) // arrasta a borda direita além da esquerda
    expect(r.width).toBeCloseTo(MIN_BOX_SIZE)
  })

  it('respeita os limites da imagem', () => {
    const r = resizeBox(base, 'se', 1.5, 1.5)
    expect(r.xCenter + r.width / 2).toBeLessThanOrEqual(1)
    expect(r.yCenter + r.height / 2).toBeLessThanOrEqual(1)
  })
})
