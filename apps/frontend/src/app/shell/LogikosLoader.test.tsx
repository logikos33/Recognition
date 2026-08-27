/**
 * A máquina de estados do loader tem de ser A MESMA do `lk-loader.js`, não uma
 * parecida. O handoff é explícito: "portar como componente React com a MESMA
 * máquina de estados".
 *
 * O que se protege aqui:
 *  · glitch SÓ em entrada/retry/saída — em `waiting` viraria loop decorativo,
 *    e o motion desta marca "termina em repouso";
 *  · `resolving` emite o evento 360ms depois, como o custom element;
 *  · spinner ≤24px (regra de medida do README);
 *  · quem não vê o rótulo (variante spinner) ainda ouve "Carregando".
 */
import { render, screen, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LogikosLoader } from './LogikosLoader'
import * as s from './LogikosLoader.css'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

const wrapDe = (c: HTMLElement) => c.querySelector(`.${s.wrap.split(' ')[0]}`)

describe('máquina de estados', () => {
  it.each(['entering', 'waiting', 'retry'] as const)('%s gira', (estado) => {
    const { container } = render(<LogikosLoader estado={estado} />)
    expect(container.innerHTML).toContain(s.girando)
  })

  it.each(['resolving', 'idle'] as const)('%s NÃO gira', (estado) => {
    const { container } = render(<LogikosLoader estado={estado} />)
    expect(wrapDe(container)?.className).not.toContain(s.girando)
  })

  it('waiting NÃO tem glitch — seria loop decorativo', () => {
    const { container } = render(<LogikosLoader estado="waiting" />)
    expect(wrapDe(container)?.className ?? '').not.toContain(s.rajada)
  })

  it.each(['entering', 'retry', 'resolving'] as const)('%s TEM glitch', (estado) => {
    const { container } = render(<LogikosLoader estado={estado} />)
    expect(wrapDe(container)?.className).toContain(s.rajada)
  })

  it('resolving emite o resolvido 360ms depois, como o custom element', () => {
    const aoResolver = vi.fn()
    render(<LogikosLoader estado="resolving" onResolvido={aoResolver} />)
    expect(aoResolver).not.toHaveBeenCalled()
    act(() => void vi.advanceTimersByTime(359))
    expect(aoResolver).not.toHaveBeenCalled()
    act(() => void vi.advanceTimersByTime(1))
    expect(aoResolver).toHaveBeenCalledTimes(1)
  })

  it('sair de resolving antes dos 360ms NÃO emite', () => {
    const aoResolver = vi.fn()
    const { rerender } = render(<LogikosLoader estado="resolving" onResolvido={aoResolver} />)
    rerender(<LogikosLoader estado="waiting" onResolvido={aoResolver} />)
    act(() => void vi.advanceTimersByTime(1000))
    expect(aoResolver).not.toHaveBeenCalled()
  })

  it('o glitch do resolving é mais curto que o da entrada (300 vs 500)', () => {
    const { container: a } = render(<LogikosLoader estado="entering" />)
    const { container: b } = render(<LogikosLoader estado="resolving" />)
    expect((wrapDe(a) as HTMLElement).style.getPropertyValue('--lk-glitch-dur')).toBe('500ms')
    expect((wrapDe(b) as HTMLElement).style.getPropertyValue('--lk-glitch-dur')).toBe('300ms')
  })
})

describe('medidas e acessibilidade', () => {
  it('spinner nasce ≤24px', () => {
    const { container } = render(<LogikosLoader variante="spinner" />)
    const px = parseInt((wrapDe(container) as HTMLElement).style.getPropertyValue('--lk-size'), 10)
    expect(px).toBeLessThanOrEqual(24)
  })

  it('spinner não mostra rótulo, mas anuncia para leitor de tela', () => {
    render(<LogikosLoader variante="spinner" rotulo="CARREGANDO EVENTOS" />)
    expect(screen.queryByText('CARREGANDO EVENTOS')).toBeNull()
    expect(screen.getByText('Carregando')).toBeTruthy()
  })

  it('fullscreen mostra o rótulo', () => {
    render(<LogikosLoader variante="fullscreen" rotulo="CARREGANDO EVENTOS" />)
    expect(screen.getByText('CARREGANDO EVENTOS')).toBeTruthy()
  })

  it('aria-busy some quando parou de esperar', () => {
    const { rerender } = render(<LogikosLoader estado="waiting" />)
    expect(screen.getByRole('status').getAttribute('aria-busy')).toBe('true')
    rerender(<LogikosLoader estado="idle" />)
    expect(screen.getByRole('status').getAttribute('aria-busy')).toBe('false')
  })
})
