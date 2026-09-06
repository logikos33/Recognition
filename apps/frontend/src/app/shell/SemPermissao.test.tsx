import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { SemPermissao } from './SemPermissao'

const montar = (permissao: string) =>
  render(
    <MemoryRouter>
      <SemPermissao permissao={permissao} />
    </MemoryRouter>,
  )

/** Toda chave que chega aqui hoje, medida nos 5 chamadores do componente. */
const CHAVES_SERVIDAS = [
  'admin:panel',
  'cameras:configure',
  'frames:annotate',
  'training:read',
  'training:write',
]

describe('SemPermissao', () => {
  it('diz o PODER em português — a chave crua não vai para a tela (issue #810)', () => {
    const { container } = montar('cameras:configure')
    expect(screen.getByText('Sem permissão')).toBeTruthy()
    expect(screen.getByText(/permissão de configurar as câmeras/)).toBeTruthy()
    expect(container.textContent).not.toContain('cameras:configure')
    // "tenant" é o nome interno do inquilino — quem opera a fábrica não sabe
    // o que é. Mesma troca feita nas 8 telas da issue #810.
    expect(container.textContent).not.toMatch(/tenant/i)
    const voltar = screen.getByRole('link', { name: 'Voltar ao início' })
    expect(voltar.getAttribute('href')).toMatch(/^\/novo/)
  })

  it.each(CHAVES_SERVIDAS)('nenhum chamador vaza a chave: %s', (chave) => {
    const { container } = montar(chave)
    expect(container.textContent).not.toContain(chave)
    expect(container.textContent).toMatch(/Peça a quem administra o seu acesso/)
  })

  /**
   * O GUARD de verdade: chave que ninguém traduziu ainda. Sem o texto
   * genérico, um chamador novo volta a pintar a chave na tela — e a régua
   * `semJargao` é cega a isso por construção (`{permissao}` é expressão).
   */
  it('chave desconhecida cai no genérico em vez de vazar a chave', () => {
    const { container } = montar('operations:mandar_ver')
    expect(container.textContent).not.toContain('operations:mandar_ver')
    expect(screen.getByText(/não tem permissão para abrir esta área/i)).toBeTruthy()
  })

  it('não promete "Solicitar acesso" — o backend não tem onde registrar o pedido', () => {
    montar('frames:annotate')
    expect(screen.queryByText(/solicitar acesso/i)).toBeNull()
  })
})
