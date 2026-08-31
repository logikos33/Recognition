/**
 * O gate é o que não pode falhar aqui: o Estúdio é a casa do trainer e a
 * fronteira do jargão de ML — analyst e viewer não entram.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ can: vi.fn((_p: string) => true) }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

import { Estudio } from './Estudio'

function monta() {
  return render(
    <MemoryRouter initialEntries={['/novo/estudio/dados']}>
      <Routes>
        <Route path="/novo/estudio" element={<Estudio />}>
          <Route path="dados" element={<div>conteudo-dados</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('Estudio (layout + gate)', () => {
  beforeEach(() => {
    auth.can.mockReset()
    auth.can.mockReturnValue(true)
  })

  it('sem frames:annotate → Sem permissão, e NADA do conteúdo vaza', () => {
    auth.can.mockImplementation((p: string) => p !== 'frames:annotate')
    monta()
    expect(screen.getByText('Sem permissão')).toBeTruthy()
    expect(screen.getByText('frames:annotate')).toBeTruthy()
    expect(screen.queryByText('conteudo-dados')).toBeNull()
    expect(screen.queryByRole('navigation')).toBeNull()
  })

  it('com frames:annotate → lateral própria com Dados e a sub-rota no Outlet', () => {
    monta()
    expect(auth.can).toHaveBeenCalledWith('frames:annotate')
    const lateral = screen.getByRole('navigation', { name: 'Seções do Estúdio' })
    expect(lateral).toBeTruthy()
    expect(screen.getByRole('link', { name: /dados/i })).toBeTruthy()
    expect(screen.getByText('conteudo-dados')).toBeTruthy()
  })

  it('"Voltar" é o primeiro link da lateral e leva ao Dashboard EPI', () => {
    // A lateral do Estúdio SUBSTITUI a nav principal do Shell — sem este
    // link, quem entra aqui não tem caminho de volta nenhum (regra global,
    // ver app/shell/becoSemSaida.test.tsx).
    monta()
    const primeiro = screen.getAllByRole('link')[0]
    expect(primeiro.textContent?.trim()).toBe('Voltar')
    expect(primeiro.getAttribute('href')).toBe('/novo/epi/dashboard')
  })
})
