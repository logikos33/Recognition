/**
 * Regressão do tema em conteúdo portalizado.
 *
 * O vanilla-extract escopa os tokens à classe do tema. Enquanto essa classe
 * ficava num <div> DENTRO da app, tudo que o Radix portaliza para o <body>
 * (Modal, Tooltip, Popover, AppDrawer) nascia fora do escopo e todo `vars.*`
 * resolvia para vazio — painel transparente, sem borda, overlay sem
 * escurecimento. Este teste tranca a classe no <html>.
 *
 * O themeStore é mockado de propósito: ele usa persist/localStorage, que não é
 * o que está sob teste aqui — o alvo é onde o AppShell PÕE a classe.
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, cleanup } from '@testing-library/react'

let mockMode = 'recognition-dark'

vi.mock('../../stores/themeStore', () => ({
  useThemeStore: (selector: (s: { mode: string }) => unknown) =>
    selector({ mode: mockMode }),
}))

const { AppShell } = await import('../../components/layout/AppShell/AppShell')
const { recognitionDarkTheme } = await import(
  '../../theme/tokens/recognition-dark.css'
)
const { cyberpunkTheme } = await import('../../styles/themes/cyberpunk.css')

describe('AppShell — escopo do tema', () => {
  afterEach(() => {
    cleanup()
    mockMode = 'recognition-dark'
    document.documentElement.classList.remove(recognitionDarkTheme, cyberpunkTheme)
  })

  it('aplica a classe de tema no documentElement, não só num div interno', () => {
    render(<AppShell><div>conteudo</div></AppShell>)

    // É isto que faz o portal (renderizado no body) enxergar os tokens.
    expect(
      document.documentElement.classList.contains(recognitionDarkTheme),
    ).toBe(true)
  })

  it('mantém o data-theme para seletores CSS', () => {
    render(<AppShell><div>conteudo</div></AppShell>)
    expect(document.documentElement.getAttribute('data-theme')).toBe(
      'recognition-dark',
    )
  })

  it('troca de tema substitui a classe, sem acumular as duas', () => {
    const first = render(<AppShell><div>c</div></AppShell>)
    expect(
      document.documentElement.classList.contains(recognitionDarkTheme),
    ).toBe(true)
    first.unmount()

    mockMode = 'cyberpunk'
    render(<AppShell><div>c</div></AppShell>)

    expect(document.documentElement.classList.contains(cyberpunkTheme)).toBe(true)
    expect(
      document.documentElement.classList.contains(recognitionDarkTheme),
    ).toBe(false)
    expect(document.documentElement.getAttribute('data-theme')).toBe('cyberpunk')
  })

  it('não remove classes de terceiros do <html>', () => {
    document.documentElement.classList.add('classe-de-extensao')
    render(<AppShell><div>conteudo</div></AppShell>)

    expect(
      document.documentElement.classList.contains('classe-de-extensao'),
    ).toBe(true)
    document.documentElement.classList.remove('classe-de-extensao')
  })
})
