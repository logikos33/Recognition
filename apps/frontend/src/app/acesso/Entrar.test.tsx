/**
 * O que esta tela não pode errar: mandar credenciais erradas ao invés de
 * chamar `useAuth().login`, esconder o erro do backend, e inventar uma
 * contagem de tentativas que a API não devolve.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const login = vi.fn()
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => ({ login }) }))

import { Entrar } from './Entrar'

const montar = () => render(<MemoryRouter><Entrar /></MemoryRouter>)

beforeEach(() => {
  login.mockReset()
})

describe('Entrar — login do front novo', () => {
  it('chama login com email, senha e o destino do front novo (rotaNova)', async () => {
    login.mockResolvedValue({ id: '1' })
    montar()
    fireEvent.change(screen.getByPlaceholderText('voce@empresa.com.br'), {
      target: { value: 'ana@rvb.com.br' },
    })
    fireEvent.change(screen.getByPlaceholderText('••••••••'), {
      target: { value: 'segredo123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    await waitFor(() =>
      expect(login).toHaveBeenCalledWith('ana@rvb.com.br', 'segredo123', '/'),
    )
  })

  it('erro do backend aparece na tela, sem inventar contagem de tentativas', async () => {
    login.mockRejectedValue(new Error('Credenciais inválidas'))
    montar()
    fireEvent.change(screen.getByPlaceholderText('voce@empresa.com.br'), {
      target: { value: 'ana@rvb.com.br' },
    })
    fireEvent.change(screen.getByPlaceholderText('••••••••'), {
      target: { value: 'errada' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByText('Credenciais inválidas')).toBeTruthy()
    // A prancha inventa "3 tentativas restantes" — o backend não devolve isso.
    expect(screen.queryByText(/tentativas restantes/i)).toBeNull()
  })

  it('erro sem Error real cai na mensagem genérica honesta', async () => {
    login.mockRejectedValue('boom')
    montar()
    fireEvent.change(screen.getByPlaceholderText('voce@empresa.com.br'), {
      target: { value: 'ana@rvb.com.br' },
    })
    fireEvent.change(screen.getByPlaceholderText('••••••••'), {
      target: { value: 'x' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByText('Erro ao autenticar')).toBeTruthy()
  })

  it('link "Esqueci minha senha" leva à tela nova de recuperação', () => {
    montar()
    const link = screen.getByText('Esqueci minha senha') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/esqueci-senha')
  })
})
