/**
 * Tests: alerta de desbalanceamento de classes (lógica pura).
 */
import { describe, expect, it } from 'vitest'
import { computeImbalance, imbalanceMessages } from '../../utils/classImbalance'

describe('computeImbalance', () => {
  it('grita quando max ≥ 10× min entre classes com uso > 0', () => {
    const r = computeImbalance([
      { name: 'capacete', usage: 400 },
      { name: 'luva', usage: 12 },
      { name: 'colete', usage: 200 },
    ])
    expect(r.triggered).toBe(true)
    expect(r.max?.name).toBe('capacete')
    expect(r.rare.map(c => c.name)).toEqual(['luva'])
  })

  it('não grita quando o uso é equilibrado', () => {
    const r = computeImbalance([
      { name: 'capacete', usage: 100 },
      { name: 'luva', usage: 40 },
    ])
    expect(r.triggered).toBe(false)
    expect(r.rare).toHaveLength(0)
  })

  it('classe ativa com 0 caixas dispara — mas só depois que a anotação começou', () => {
    const started = computeImbalance([
      { name: 'capacete', usage: 50 },
      { name: 'óculos', usage: 0 },
    ])
    expect(started.triggered).toBe(true)
    expect(started.zeroUsage).toEqual(['óculos'])

    // Projeto zerado (nenhuma caixa em nada) não é desbalanceamento
    const fresh = computeImbalance([
      { name: 'capacete', usage: 0 },
      { name: 'óculos', usage: 0 },
    ])
    expect(fresh.triggered).toBe(false)
  })

  it('lista vazia não dispara', () => {
    expect(computeImbalance([]).triggered).toBe(false)
  })
})

describe('imbalanceMessages', () => {
  it('nomeia a classe rara com números', () => {
    const msgs = imbalanceMessages(
      computeImbalance([
        { name: 'capacete', usage: 400 },
        { name: 'luva', usage: 12 },
      ]),
    )
    expect(msgs[0]).toBe('luva tem 12 caixas; capacete tem 400 — o modelo vai ignorar luva.')
  })

  it('nomeia classes zeradas', () => {
    const msgs = imbalanceMessages(
      computeImbalance([
        { name: 'capacete', usage: 50 },
        { name: 'óculos', usage: 0 },
      ]),
    )
    expect(msgs.some(m => m.includes('óculos'))).toBe(true)
  })

  it('sem alerta → sem mensagens', () => {
    expect(imbalanceMessages(computeImbalance([]))).toEqual([])
  })
})
