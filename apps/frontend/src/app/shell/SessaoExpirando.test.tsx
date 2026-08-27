/**
 * O que se protege aqui não é layout — é o comportamento que, quebrado, ou
 * derruba o app ou desloga alguém no meio do turno:
 *
 *  · o aviso é de 5 MINUTOS, não "perto do fim" — antes disso não aparece;
 *  · o contador anda de segundo em segundo, em mm:ss com zero à esquerda;
 *  · `onExpirou` sai UMA vez. Em loop, viraria cascata de logout;
 *  · desmontar mata o intervalo. Timer órfão em SPA de turno de 8h vaza.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SessaoExpirando } from './SessaoExpirando'

const MIN = 60_000

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-08-27T12:00:00Z'))
})
afterEach(() => vi.useRealTimers())

/** Avança o relógio deixando o React reagir a cada batida. */
const avancar = (ms: number) => act(() => void vi.advanceTimersByTime(ms))

const montar = (restanteMs: number, props: Partial<Parameters<typeof SessaoExpirando>[0]> = {}) =>
  render(
    <SessaoExpirando
      expiraEm={Date.now() + restanteMs}
      onRenovar={props.onRenovar ?? vi.fn()}
      onSair={props.onSair ?? vi.fn()}
      onExpirou={props.onExpirou}
    />,
  )

describe('quando aparece', () => {
  it('fica calado com mais de 5 min restantes', () => {
    montar(5 * MIN + 1000)
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('aparece exatamente em 5 min', () => {
    montar(5 * MIN)
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    expect(screen.getByText('05:00')).toBeTruthy()
  })

  it('aparece sozinho quando o relógio cruza os 5 min', () => {
    montar(5 * MIN + 2000)
    expect(screen.queryByRole('alertdialog')).toBeNull()
    avancar(3000)
    expect(screen.getByRole('alertdialog')).toBeTruthy()
  })
})

describe('contador', () => {
  it('desce de segundo em segundo', () => {
    montar(5 * MIN)
    avancar(1000)
    expect(screen.getByText('04:59')).toBeTruthy()
    avancar(1000)
    expect(screen.getByText('04:58')).toBeTruthy()
  })

  it('formata mm:ss com zero à esquerda', () => {
    montar(9000)
    expect(screen.getByText('00:09')).toBeTruthy()
    avancar(1000)
    expect(screen.getByText('00:08')).toBeTruthy()
  })

  it('some ao zerar — não fica um 00:00 pendurado', () => {
    montar(2000)
    avancar(2000)
    expect(screen.queryByText('00:00')).toBeNull()
    expect(screen.getByRole('alertdialog')).toBeTruthy()
  })

  it('é polite, não assertive — leitor de tela não pode ser atropelado 300 vezes', () => {
    const { container } = montar(5 * MIN)
    expect(container.querySelector('[aria-live]')?.getAttribute('aria-live')).toBe('polite')
  })
})

describe('expiração', () => {
  it('chama onExpirou UMA vez, mesmo passando muito tempo depois', () => {
    const aoExpirar = vi.fn()
    montar(3000, { onExpirou: aoExpirar })
    avancar(2999)
    expect(aoExpirar).not.toHaveBeenCalled()
    avancar(1)
    expect(aoExpirar).toHaveBeenCalledTimes(1)
    avancar(10 * MIN)
    expect(aoExpirar).toHaveBeenCalledTimes(1)
  })

  it('para de contar depois de zerar', () => {
    montar(1000, { onExpirou: vi.fn() })
    avancar(1000)
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('ações', () => {
  it('Renovar e Sair chamam os callbacks', () => {
    const renovar = vi.fn()
    const sair = vi.fn()
    montar(2 * MIN, { onRenovar: renovar, onSair: sair })
    fireEvent.click(screen.getByRole('button', { name: /renovar/i }))
    fireEvent.click(screen.getByRole('button', { name: /sair/i }))
    expect(renovar).toHaveBeenCalledTimes(1)
    expect(sair).toHaveBeenCalledTimes(1)
  })

  it('o foco cai no Renovar assim que o aviso abre', () => {
    montar(2 * MIN)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /renovar/i }))
  })
})

describe('desmonte', () => {
  it('não deixa timer vivo', () => {
    const aoExpirar = vi.fn()
    const { unmount } = montar(2 * MIN, { onExpirou: aoExpirar })
    // Delta, não contagem absoluta: o `focus()` do jsdom também agenda um
    // timer, e travar num número exato seria testar o jsdom, não o componente.
    const antes = vi.getTimerCount()
    unmount()
    expect(vi.getTimerCount()).toBe(antes - 1)
    avancar(10 * MIN)
    expect(aoExpirar).not.toHaveBeenCalled()
  })
})
