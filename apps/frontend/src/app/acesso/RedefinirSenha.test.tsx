/**
 * O que esta tela não pode errar: deixar submeter senha abaixo do mínimo real
 * do backend (6 chars), mandar payload sem `token`, e reprovar uma senha
 * válida por causa de uma regra "letras e números" que o backend não exige.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const post = vi.fn()
vi.mock('../../services/api', () => ({ api: { post: (...a: unknown[]) => post(...a) } }))

import { RedefinirSenha } from './RedefinirSenha'

const montar = (busca = '?token=abc123') =>
  render(
    <MemoryRouter initialEntries={[`/novo/redefinir-senha${busca}`]}>
      <Routes>
        <Route path="/novo/redefinir-senha" element={<RedefinirSenha />} />
      </Routes>
    </MemoryRouter>,
  )

const preencher = (senha: string, confirmar: string) => {
  fireEvent.change(screen.getByLabelText('Nova senha'), { target: { value: senha } })
  fireEvent.change(screen.getByLabelText('Confirmar nova senha'), { target: { value: confirmar } })
}

const botaoSalvar = () =>
  screen.getByRole('button', { name: /salvar e entrar/i }) as HTMLButtonElement

beforeEach(() => {
  post.mockReset()
})

describe('RedefinirSenha — redefinição do front novo', () => {
  it('sem token na query, mostra link inválido — não deixa preencher senha', () => {
    montar('')
    expect(screen.getByRole('heading', { name: /link inválido/i })).toBeTruthy()
    expect(screen.queryByLabelText('Nova senha')).toBeNull()
  })

  it('botão fica desabilitado com senha abaixo do mínimo real (6 chars)', () => {
    montar()
    expect(botaoSalvar().disabled).toBe(true)
    preencher('12345', '12345') // 5 chars: abaixo do mínimo real
    expect(botaoSalvar().disabled).toBe(true)
  })

  it('com 6 chars e confirmação igual, habilita e envia {token, password}', async () => {
    post.mockResolvedValue({ success: true })
    montar('?token=xyz789')
    preencher('abcdef', 'abcdef')
    expect(botaoSalvar().disabled).toBe(false)
    fireEvent.click(botaoSalvar())
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/auth/reset-password', { token: 'xyz789', password: 'abcdef' }),
    )
  })

  it('senhas diferentes mantêm o botão desabilitado', () => {
    montar()
    preencher('abcdef', 'abcxyz')
    expect(botaoSalvar().disabled).toBe(true)
  })

  it('sucesso mostra o link para a tela nova de login', async () => {
    post.mockResolvedValue({ success: true })
    montar()
    preencher('abcdef', 'abcdef')
    fireEvent.click(botaoSalvar())
    const link = (await screen.findByText(/ir para o login/i)) as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/novo/entrar')
  })

  it('não exige "letras e números" — só o mínimo real de 6 chars é a barreira', () => {
    // Regressão: a prancha pede complexidade que o backend NÃO valida
    // (password_reset_service.py:83-84). Uma senha só de dígitos, com 6+
    // chars e confirmação igual, tem de habilitar o botão.
    montar()
    preencher('999999', '999999')
    expect(botaoSalvar().disabled).toBe(false)
  })

  it('erro do backend (token expirado) aparece na tela', async () => {
    post.mockRejectedValue(new Error('Token inválido ou expirado'))
    montar()
    preencher('abcdef', 'abcdef')
    fireEvent.click(botaoSalvar())
    expect(await screen.findByText('Token inválido ou expirado')).toBeTruthy()
  })
})
