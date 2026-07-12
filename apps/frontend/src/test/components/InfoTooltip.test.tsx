import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it } from 'vitest'
import { InfoTooltip } from '../../components/ui/InfoTooltip/InfoTooltip'

// Radix Popper depende de ResizeObserver, ausente no jsdom
beforeAll(() => {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  ;(globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverMock
})

describe('InfoTooltip', () => {
  it('renderiza botão acessível com aria-label descritivo', () => {
    render(<InfoTooltip text="Explicação do campo" />)
    const btn = screen.getByRole('button', { name: 'Mais informações: Explicação do campo' })
    expect(btn).toBeDefined()
    expect(btn.getAttribute('type')).toBe('button')
  })

  it('usa o título no aria-label quando presente', () => {
    render(<InfoTooltip title="Épocas" text="Quantas vezes o modelo revê o dataset" />)
    expect(screen.getByRole('button', { name: 'Mais informações: Épocas' })).toBeDefined()
  })

  it('mostra o conteúdo ao receber foco (acessível por teclado)', async () => {
    render(<InfoTooltip title="Confiança mínima" text="Só exibe detecções acima deste valor" />)
    const btn = screen.getByRole('button', { name: 'Mais informações: Confiança mínima' })

    fireEvent.focus(btn)

    // Radix duplica o conteúdo (visual + span para leitores de tela)
    const bodies = await screen.findAllByText('Só exibe detecções acima deste valor')
    expect(bodies.length).toBeGreaterThan(0)
    const titles = await screen.findAllByText('Confiança mínima')
    expect(titles.length).toBeGreaterThan(0)
  })

  it('não mostra o conteúdo sem hover/focus (nunca fixo)', () => {
    render(<InfoTooltip text="Ajuda oculta por padrão" />)
    expect(screen.queryByText('Ajuda oculta por padrão')).toBeNull()
  })
})
