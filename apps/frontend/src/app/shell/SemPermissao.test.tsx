import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { rotaNova } from '../RotasNovas'
import { SemPermissao } from './SemPermissao'

describe('SemPermissao', () => {
  it('orienta com a chave exata e o caminho de volta', () => {
    render(
      <MemoryRouter>
        <SemPermissao permissao="frames:annotate" />
      </MemoryRouter>,
    )
    expect(screen.getByText('Sem permissão')).toBeTruthy()
    expect(screen.getByText('frames:annotate')).toBeTruthy()
    const voltar = screen.getByRole('link', { name: 'Voltar ao início' })
    // rotaNova('/') — comparado contra a mesma função que SemPermissao.tsx usa,
    // não contra um `/^\/novo/` fixo que quebrou quando o prefixo virou identidade.
    expect(voltar.getAttribute('href')).toBe(rotaNova('/'))
  })

  it('não promete "Solicitar acesso" — o backend não tem onde registrar o pedido', () => {
    render(
      <MemoryRouter>
        <SemPermissao permissao="frames:annotate" />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/solicitar acesso/i)).toBeNull()
  })
})
