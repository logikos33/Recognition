/**
 * O que esta tela não pode errar: mandar payload diferente do que o backend
 * espera, e vazar se o e-mail existe ou não (o backend é sempre "sucesso").
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const post = vi.fn()
vi.mock('../../services/api', () => ({ api: { post: (...a: unknown[]) => post(...a) } }))

import { EsqueciSenha } from './EsqueciSenha'

const montar = () => render(<MemoryRouter><EsqueciSenha /></MemoryRouter>)

beforeEach(() => {
  post.mockReset()
})

describe('EsqueciSenha — recuperação do front novo', () => {
  it('envia o payload {email} igual ao ForgotPasswordPage antigo', async () => {
    post.mockResolvedValue({ success: true })
    montar()
    fireEvent.change(screen.getByPlaceholderText('voce@empresa.com.br'), {
      target: { value: 'ana@rvb.com.br' },
    })
    fireEvent.click(screen.getByRole('button', { name: /enviar link/i }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/auth/forgot-password', { email: 'ana@rvb.com.br' }),
    )
  })

  it('estado pós-envio mostra o TTL real de 30 minutos (Redis, não a prancha)', async () => {
    post.mockResolvedValue({ success: true })
    montar()
    fireEvent.change(screen.getByPlaceholderText('voce@empresa.com.br'), {
      target: { value: 'ana@rvb.com.br' },
    })
    fireEvent.click(screen.getByRole('button', { name: /enviar link/i }))
    expect(await screen.findByText(/verifique seu e-mail/i)).toBeTruthy()
    expect(screen.getByText(/vale por 30 minutos/i)).toBeTruthy()
  })

  it('erro de rede mostra mensagem, sem travar em "enviando"', async () => {
    post.mockRejectedValue(new Error('Timeout na requisicao'))
    montar()
    fireEvent.change(screen.getByPlaceholderText('voce@empresa.com.br'), {
      target: { value: 'ana@rvb.com.br' },
    })
    fireEvent.click(screen.getByRole('button', { name: /enviar link/i }))
    expect(await screen.findByText('Timeout na requisicao')).toBeTruthy()
    const botao = screen.getByRole('button', { name: /enviar link/i }) as HTMLButtonElement
    expect(botao.disabled).toBe(false)
  })

  it('voltar ao login leva para a tela nova, não para a antiga', () => {
    montar()
    const link = screen.getByText(/voltar ao login/i) as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/entrar')
  })
})
