/**
 * Testes Vitest/RTL para ResetPasswordPage (ADR-0042 Fase 2).
 *
 * Padrão: api.ts mockado; nenhuma chamada de rede real.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ResetPasswordPage } from '../../pages/ResetPasswordPage'

vi.mock('../../services/api', () => ({
  api: { post: vi.fn() },
}))

import { api } from '../../services/api'

function renderWithToken(token: string | null) {
  const path = token ? `/reset-password?token=${token}` : '/reset-password'
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset()
  })

  it('sem token na URL, mostra erro e não renderiza o formulário', () => {
    renderWithToken(null)
    expect(screen.getByText(/Link inválido/i)).toBeTruthy()
    expect(screen.queryByPlaceholderText('Nova senha')).toBeNull()
  })

  it('bloqueia envio se as senhas não coincidem', () => {
    renderWithToken('goodtoken')
    fireEvent.change(screen.getByPlaceholderText('Nova senha'), { target: { value: 'abc12345' } })
    fireEvent.change(screen.getByPlaceholderText('Confirmar nova senha'), { target: { value: 'diferente' } })
    fireEvent.click(screen.getByText('Redefinir senha'))

    expect(screen.getByText(/não coincidem/i)).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('com senhas coincidentes, chama a API com token e senha e mostra sucesso', async () => {
    vi.mocked(api.post).mockResolvedValue({ success: true })
    renderWithToken('goodtoken')

    fireEvent.change(screen.getByPlaceholderText('Nova senha'), { target: { value: 'abc12345' } })
    fireEvent.change(screen.getByPlaceholderText('Confirmar nova senha'), { target: { value: 'abc12345' } })
    fireEvent.click(screen.getByText('Redefinir senha'))

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/reset-password', {
        token: 'goodtoken',
        password: 'abc12345',
      })
    })
    expect(await screen.findByText(/redefinida com sucesso/i)).toBeTruthy()
  })

  it('exibe erro retornado pela API (ex.: token expirado)', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('Token inválido ou expirado'))
    renderWithToken('badtoken')

    fireEvent.change(screen.getByPlaceholderText('Nova senha'), { target: { value: 'abc12345' } })
    fireEvent.change(screen.getByPlaceholderText('Confirmar nova senha'), { target: { value: 'abc12345' } })
    fireEvent.click(screen.getByText('Redefinir senha'))

    expect(await screen.findByText(/Token inválido ou expirado/i)).toBeTruthy()
  })
})
