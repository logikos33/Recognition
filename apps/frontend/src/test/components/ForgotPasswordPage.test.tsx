/**
 * Testes Vitest/RTL para ForgotPasswordPage (ADR-0042 Fase 2).
 *
 * Padrão: api.ts mockado; nenhuma chamada de rede real.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ForgotPasswordPage } from '../../pages/ForgotPasswordPage'

vi.mock('../../services/api', () => ({
  api: { post: vi.fn() },
}))

import { api } from '../../services/api'

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset()
  })

  it('envia o e-mail informado e mostra mensagem neutra de sucesso', async () => {
    vi.mocked(api.post).mockResolvedValue({ success: true })
    render(<MemoryRouter><ForgotPasswordPage /></MemoryRouter>)

    fireEvent.change(screen.getByPlaceholderText('seu@email.com'), {
      target: { value: 'user@test.com' },
    })
    fireEvent.click(screen.getByText('Enviar link de redefinição'))

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/forgot-password', { email: 'user@test.com' })
    })
    expect(await screen.findByText(/receberá um link de/i)).toBeTruthy()
  })

  it('exibe erro se a request falhar', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('Timeout na requisicao'))
    render(<MemoryRouter><ForgotPasswordPage /></MemoryRouter>)

    fireEvent.change(screen.getByPlaceholderText('seu@email.com'), {
      target: { value: 'user@test.com' },
    })
    fireEvent.click(screen.getByText('Enviar link de redefinição'))

    expect(await screen.findByText(/Timeout na requisicao/i)).toBeTruthy()
  })
})
