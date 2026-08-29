/**
 * DECISÃO v2 item 3: a cor de marca do tenant tem de passar de 4,5:1 contra as
 * superfícies do shell escuro — cor reprovada sofre clamp de luminância.
 *
 * O caso que motivou a regra é real: o tenant RVB tem `#06b6d4` no cadastro.
 */
import { describe, expect, it } from 'vitest'

import { PISO_CONTRASTE, contraste, corDeMarcaUsavel, piorContraste } from './contraste'

describe('piso de contraste da marca', () => {
  it('cor que já passa não é tocada', () => {
    // O ciano do desenho passa com folga contra #0A0A0F e #14141C.
    const r = corDeMarcaUsavel('#00E5FF')
    expect(r.ajustada).toBe(false)
    expect(r.cor.toLowerCase()).toBe('#00e5ff')
    expect(r.contraste!).toBeGreaterThanOrEqual(PISO_CONTRASTE)
  })

  it('cor escura demais é CLAREADA até passar — nunca escurecida', () => {
    // Azul-marinho: a marca legítima de muita indústria, e invisível no escuro.
    const escura = '#0B1F3A'
    expect(piorContraste(escura)!).toBeLessThan(PISO_CONTRASTE)

    const r = corDeMarcaUsavel(escura)
    expect(r.ajustada).toBe(true)
    expect(r.contraste!).toBeGreaterThanOrEqual(PISO_CONTRASTE)
    // Clareou de verdade: a luminância final é maior que a inicial.
    expect(piorContraste(r.cor)!).toBeGreaterThan(piorContraste(escura)!)
  })

  it('preserva o matiz — a marca continua reconhecível', () => {
    // Um vermelho escuro tem de continuar vermelho depois do clamp: o canal
    // dominante segue dominante. Clarear não pode virar lavar tudo de branco.
    const r = corDeMarcaUsavel('#3A0A0A')
    const [vr, vg, vb] = [1, 3, 5].map((i) => Number.parseInt(r.cor.slice(i, i + 2), 16))
    expect(vr).toBeGreaterThan(vg)
    expect(vr).toBeGreaterThan(vb)
  })

  it('o caso real do RVB (#06b6d4) é avaliado, não chutado', () => {
    const r = corDeMarcaUsavel('#06b6d4')
    expect(r.contraste!).toBeGreaterThanOrEqual(PISO_CONTRASTE)
    // Se já passava, não deve ter sido mexida.
    if (piorContraste('#06b6d4')! >= PISO_CONTRASTE) expect(r.ajustada).toBe(false)
  })

  it('cor inválida ou ausente cai no ciano do desenho, sem quebrar', () => {
    for (const ruim of [null, undefined, '', 'azul', '#12']) {
      const r = corDeMarcaUsavel(ruim as string | null)
      expect(r.cor.toLowerCase()).toBe('#00e5ff')
    }
  })

  it('o contraste é medido contra a PIOR superfície, não a melhor', () => {
    // #14141C é mais claro que #0A0A0F: uma cor pode passar contra um e não
    // contra o outro. Quem manda é o pior caso — senão o botão some no card.
    const c = '#2A2A40'
    expect(piorContraste(c)).toBe(Math.min(contraste(c, '#0A0A0F')!, contraste(c, '#14141C')!))
  })
})
