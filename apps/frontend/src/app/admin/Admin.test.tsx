/**
 * O gate é o que não pode falhar aqui: `admin:panel` é superadmin-only
 * (`permissions.py:205-208`) — nem `admin` do tenant entra.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ can: vi.fn((_p: string) => true) }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

import { Admin } from './Admin'

function monta() {
  return render(
    <MemoryRouter initialEntries={['/novo/admin']}>
      <Routes>
        <Route path="/novo/admin" element={<Admin />}>
          <Route index element={<div>conteudo-visao-geral</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('Admin (layout + gate)', () => {
  beforeEach(() => {
    auth.can.mockReset()
    auth.can.mockReturnValue(true)
  })

  it('sem admin:panel (ex.: admin do tenant) → Sem permissão, e NADA do conteúdo vaza', () => {
    auth.can.mockImplementation((p: string) => p !== 'admin:panel')
    monta()
    expect(screen.getByText('Sem permissão')).toBeTruthy()
    expect(screen.getByText('admin:panel')).toBeTruthy()
    expect(screen.queryByText('conteudo-visao-geral')).toBeNull()
    expect(screen.queryByRole('navigation')).toBeNull()
  })

  it('com admin:panel (superadmin) → lateral própria com Visão geral e o Outlet', () => {
    monta()
    expect(auth.can).toHaveBeenCalledWith('admin:panel')
    const lateral = screen.getByRole('navigation', { name: 'Seções do Admin' })
    expect(lateral).toBeTruthy()
    expect(screen.getByRole('link', { name: /visão geral/i })).toBeTruthy()
    expect(screen.getByText('conteudo-visao-geral')).toBeTruthy()
  })
})
