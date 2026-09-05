/**
 * Testes Vitest/RTL para a tela de entrada (bloco 4 — armadilhas da entrada).
 *
 * O que estes testes travam: a aba "Criar Conta" não volta. Ela chamava
 * POST /api/auth/register, que criava usuário com role='operator' e SEM
 * tenant_id — e o próprio /auth/login depois recusava essa conta
 * ("Usuário sem tenant atribuído", ADR-0017). Quem errasse a aba ficava
 * com uma conta que não entra em lugar nenhum, sem saber por quê.
 *
 * Padrão: useAuth mockado; nenhuma chamada de rede real.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { Login } from '../../pages/Login'

const login = vi.fn()
const register = vi.fn()

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ login, register }),
}))

describe('Login — sem porta para conta órfã', () => {
  beforeEach(() => {
    login.mockReset()
    register.mockReset()
  })

  it('não oferece aba "Criar Conta"', () => {
    render(<MemoryRouter><Login /></MemoryRouter>)
    expect(screen.queryByText(/criar conta/i)).toBeNull()
  })

  it('nenhum clique na tela revela o formulário de cadastro', () => {
    render(<MemoryRouter><Login /></MemoryRouter>)
    // Antes, clicar na aba "Criar Conta" trocava o formulário e fazia
    // aparecer "Nome completo" e "Confirmar senha".
    for (const btn of screen.getAllByRole('button')) fireEvent.click(btn)
    expect(screen.queryByPlaceholderText(/nome completo/i)).toBeNull()
    expect(screen.queryByPlaceholderText(/confirmar senha/i)).toBeNull()
  })

  it('nenhuma interação com a tela chama register()', async () => {
    render(<MemoryRouter><Login /></MemoryRouter>)
    for (const btn of screen.getAllByRole('button')) fireEvent.click(btn)
    fireEvent.submit(document.querySelector('form') as HTMLFormElement)
    await waitFor(() => expect(register).not.toHaveBeenCalled())
  })

  it('ainda entra: submit chama login com e-mail e senha', async () => {
    login.mockResolvedValue({ id: '1' })
    render(<MemoryRouter><Login /></MemoryRouter>)

    fireEvent.change(screen.getByPlaceholderText('seu@email.com'), {
      target: { value: 'operador@rvb.test' },
    })
    fireEvent.change(screen.getByPlaceholderText('••••••••'), {
      target: { value: 'senha123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith('operador@rvb.test', 'senha123')
    })
  })

  it('mantém o caminho de "Esqueci minha senha"', () => {
    render(<MemoryRouter><Login /></MemoryRouter>)
    const link = screen.getByText('Esqueci minha senha')
    expect(link.getAttribute('href')).toBe('/forgot-password')
  })
})
