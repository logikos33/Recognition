/**
 * ProcedenciaBadge — classificação honesta de procedência do evento (defeito 3).
 *
 * Cobre a função pura (limiar, dado faltante, relógio fora, formatos de data
 * divergentes entre /api/alerts e /api/v1/events) e a regra de renderização:
 * a tela NUNCA afirma "ao vivo" — só marca o que é comprovadamente retroativo.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  ProcedenciaBadge,
  classificarLatencia,
} from '../../components/shared/ProcedenciaBadge'

// Mesmo instante nos dois formatos que o backend produz hoje.
const RFC822 = 'Mon, 24 Aug 2026 12:00:00 GMT'
const ISO_NAIVE = '2026-08-24T12:00:00'

/**
 * Roda `fn` com o fuso do PROCESSO forçado. Node relê `process.env.TZ` a cada
 * operação de Date, então isto vale dentro do worker do vitest — e é o que
 * torna o teste de normalização independente do TZ de quem roda.
 */
function comFuso<T>(tz: string, fn: () => T): T {
  const anterior = process.env.TZ
  process.env.TZ = tz
  try {
    return fn()
  } finally {
    process.env.TZ = anterior
  }
}

describe('classificarLatencia', () => {
  it('captura e gravação simultâneas → ao-vivo', () => {
    expect(classificarLatencia(RFC822, RFC822)).toBe('ao-vivo')
  })

  it('atraso de 2 min fica abaixo do limiar → ao-vivo', () => {
    expect(classificarLatencia(RFC822, 'Mon, 24 Aug 2026 12:02:00 GMT')).toBe(
      'ao-vivo',
    )
  })

  it('atraso exatamente no limiar (5 min) já conta como retroativa', () => {
    expect(classificarLatencia(RFC822, 'Mon, 24 Aug 2026 12:05:00 GMT')).toBe(
      'retroativa',
    )
  })

  it('frame coletado há dias e gravado agora → retroativa', () => {
    expect(classificarLatencia(RFC822, 'Thu, 27 Aug 2026 09:31:00 GMT')).toBe(
      'retroativa',
    )
  })

  it('limiar customizado é respeitado', () => {
    expect(
      classificarLatencia(RFC822, 'Mon, 24 Aug 2026 12:02:00 GMT', 60_000),
    ).toBe('retroativa')
  })

  it('sem hora de captura → desconhecida (não inventa "ao vivo")', () => {
    expect(classificarLatencia(undefined, RFC822)).toBe('desconhecida')
    expect(classificarLatencia(null, RFC822)).toBe('desconhecida')
    expect(classificarLatencia(RFC822, null)).toBe('desconhecida')
  })

  it('data inválida → desconhecida', () => {
    expect(classificarLatencia('nao-e-data', RFC822)).toBe('desconhecida')
  })

  it('captura no futuro além do limiar (relógio do device fora) → desconhecida', () => {
    expect(classificarLatencia('Mon, 24 Aug 2026 12:30:00 GMT', RFC822)).toBe(
      'desconhecida',
    )
  })
})

/**
 * /api/alerts manda RFC 822 e /api/v1/events manda ISO naive. Sob TZ=UTC as
 * duas leituras coincidem, então afirmar "ISO naive vale UTC" sem forçar o
 * fuso passava À TOA no CI e não provava nada. Aqui o fuso é FORÇADO em dois
 * offsets de sinal oposto: sem a normalização, um vira 'desconhecida'
 * (captura no futuro) e o outro vira 'retroativa'.
 */
describe('normalização de fuso — determinista em qualquer TZ do runner', () => {
  // Guarda: se a troca de fuso não pegasse, os casos abaixo voltariam a ser
  // tautológicos. Este falha ALTO em vez de deixar o teste passar vazio.
  it.each([
    ['America/Sao_Paulo', '2026-08-24T15:00:00.000Z'], // UTC−3
    ['Asia/Tokyo', '2026-08-24T03:00:00.000Z'], // UTC+9
  ])('forçar %s muda mesmo a leitura local de ISO naive', (tz, esperado) => {
    expect(comFuso(tz, () => new Date(ISO_NAIVE).toISOString())).toBe(esperado)
  })

  it.each(['America/Sao_Paulo', 'Asia/Tokyo', 'UTC'])(
    'em %s, ISO naive e RFC 822 do MESMO instante continuam ao-vivo',
    tz => {
      expect(comFuso(tz, () => classificarLatencia(ISO_NAIVE, RFC822))).toBe(
        'ao-vivo',
      )
      expect(comFuso(tz, () => classificarLatencia(RFC822, ISO_NAIVE))).toBe(
        'ao-vivo',
      )
    },
  )

  it('ISO com offset explícito não é reinterpretado', () => {
    // Mesmo instante do RFC822, escrito em BRT. Anexar 'Z' aqui seria o erro
    // simétrico — a regexp de naive não pode casar com string que tem offset.
    expect(
      comFuso('Asia/Tokyo', () =>
        classificarLatencia('2026-08-24T09:00:00-03:00', RFC822),
      ),
    ).toBe('ao-vivo')
  })
})

describe('ProcedenciaBadge', () => {
  it('marca o evento retroativo', () => {
    render(
      <ProcedenciaBadge
        capturadoEm={RFC822}
        gravadoEm="Thu, 27 Aug 2026 09:31:00 GMT"
      />,
    )
    expect(screen.getByText(/coleta retroativa/i)).toBeTruthy()
  })

  it('NÃO afirma "ao vivo" quando o atraso é pequeno — apenas não marca nada', () => {
    const { container } = render(
      <ProcedenciaBadge capturadoEm={RFC822} gravadoEm={RFC822} />,
    )
    expect(container.textContent).toBe('')
    expect(screen.queryByText(/ao vivo/i)).toBeNull()
  })

  it('sem dado de captura não marca nada', () => {
    const { container } = render(<ProcedenciaBadge gravadoEm={RFC822} />)
    expect(container.textContent).toBe('')
  })
})
