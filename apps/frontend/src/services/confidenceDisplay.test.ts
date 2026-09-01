/**
 * Contrato A1c: a confiança crua não prevê acerto (medido no DEV, ~58-65%
 * plano em toda a faixa — ver comentário de `confidenceDisplay.ts`). Este
 * teste é a prova de mutação: se alguém reinstalar o selo cru para quem não
 * é superadmin, o `not.toMatch(/%$/)` abaixo REPROVA.
 */
import { describe, expect, it } from 'vitest'

import { confiancaBruta, confiancaHonesta, confiancaInternaOuCliente } from './confidenceDisplay'

describe('confiancaInternaOuCliente (contrato A1c)', () => {
  it('superadmin vê o número cru', () => {
    expect(confiancaInternaOuCliente(1, true)).toBe('100%')
    expect(confiancaInternaOuCliente(0.873, true)).toBe('87%')
  })

  it('qualquer outro papel NUNCA vê o número cru — mesmo em 100%', () => {
    // A mutação real que já aconteceu em produção: reinstalar
    // `${Math.round(confidence * 100)}%` sem checar o papel.
    expect(confiancaInternaOuCliente(1, false)).not.toMatch(/%$/)
    expect(confiancaInternaOuCliente(1, false)).not.toBe('100%')
  })

  it('sem precisão medida, diz isso — nunca inventa e nunca mostra 0', () => {
    expect(confiancaInternaOuCliente(0.99, false)).toBe('precisão ainda não medida')
  })

  it('com precisão medida por classe, ancora a leitura nela (linguagem leiga)', () => {
    expect(confiancaInternaOuCliente(0.99, false, 0.583)).toBe(
      'de cada 10 avisos assim, ~6 são reais',
    )
  })

  it('confiança ausente é travessão para todo mundo — nunca 0%', () => {
    expect(confiancaInternaOuCliente(null, false)).toBe('—')
    expect(confiancaInternaOuCliente(undefined, true)).toBe('—')
  })
})

describe('confiancaBruta / confiancaHonesta (peças isoladas)', () => {
  it('confiancaBruta arredonda e nunca inventa quando ausente', () => {
    expect(confiancaBruta(0.583)).toBe('58%')
    expect(confiancaBruta(undefined)).toBe('—')
  })

  it('confiancaHonesta nunca devolve percentual cru', () => {
    expect(confiancaHonesta(1)).not.toMatch(/%/)
    expect(confiancaHonesta(1, 0.5)).not.toMatch(/^\d+%$/)
  })
})
