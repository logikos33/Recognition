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

// `vi.hoisted`: a factory do `vi.mock` sobe para o topo do arquivo e é
// avaliada ANTES das const comuns — sem isto, `post` é TDZ na hora do mock.
const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('../../services/api', async () => {
  const real = await vi.importActual<typeof import('../../services/api')>('../../services/api')
  return { ...real, api: { ...real.api, post } }
})

import { ApiError } from '../../services/api'
import * as estilo from './Acesso.css'
import { Entrar } from './Entrar'

const montar = () => render(<MemoryRouter><Entrar /></MemoryRouter>)

const preencherLogin = (senha = 'senha-do-papel') => {
  fireEvent.change(screen.getByPlaceholderText('voce@empresa.com.br'), {
    target: { value: 'ana@rvb.com.br' },
  })
  fireEvent.change(screen.getByPlaceholderText('••••••••'), { target: { value: senha } })
  fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))
}

beforeEach(() => {
  login.mockReset()
  post.mockReset()
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
      expect(login).toHaveBeenCalledWith('ana@rvb.com.br', 'segredo123', '/novo/'),
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
    expect(link.getAttribute('href')).toBe('/novo/esqueci-senha')
  })
})

/**
 * A saída do 403 `password_change_required` (issue #819).
 *
 * FALHA-ANTES: o 403 caía no `setErro(err.message)` como qualquer outro erro
 * — a pessoa lia "defina uma nova senha em POST /api/auth/change-password" na
 * tela de login e não tinha onde fazer isso. Como TODO caminho que arma
 * `force_password_reset` é de admin (criar tenant, criar usuário pelo painel,
 * resetar senha), a conta ficava inutilizável sem um `curl`.
 */
describe('Entrar — senha temporária', () => {
  const trocaExigida = () =>
    new ApiError('Sua senha é temporária...', 403, 'password_change_required')

  it('403 password_change_required abre o formulário de nova senha', async () => {
    login.mockRejectedValueOnce(trocaExigida())
    montar()
    preencherLogin()
    expect(await screen.findByLabelText('Nova senha')).toBeTruthy()
    expect(screen.getByLabelText('Repita a nova senha')).toBeTruthy()
  })

  it('troca a senha e entra com a nova — sem digitar credencial de novo', async () => {
    login.mockRejectedValueOnce(trocaExigida())
    post.mockResolvedValue({ success: true })
    login.mockResolvedValueOnce({ id: '1' })
    montar()
    preencherLogin()
    fireEvent.change(await screen.findByLabelText('Nova senha'), {
      target: { value: 'minha-senha-1' },
    })
    fireEvent.change(screen.getByLabelText('Repita a nova senha'), {
      target: { value: 'minha-senha-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar e entrar' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/auth/change-password', {
        email: 'ana@rvb.com.br',
        current_password: 'senha-do-papel',
        new_password: 'minha-senha-1',
      }),
    )
    await waitFor(() =>
      expect(login).toHaveBeenLastCalledWith('ana@rvb.com.br', 'minha-senha-1', '/novo/'),
    )
  })

  it('senhas diferentes não chegam à API — erro de digitação não vira senha perdida', async () => {
    login.mockRejectedValueOnce(trocaExigida())
    montar()
    preencherLogin()
    fireEvent.change(await screen.findByLabelText('Nova senha'), {
      target: { value: 'minha-senha-1' },
    })
    fireEvent.change(screen.getByLabelText('Repita a nova senha'), {
      target: { value: 'minha-senha-2' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar e entrar' }))
    expect(await screen.findByText('As duas senhas não são iguais.')).toBeTruthy()
    expect(post).not.toHaveBeenCalled()
  })

  it('a troca que falha no servidor mostra o motivo e não engole a pessoa', async () => {
    login.mockRejectedValueOnce(trocaExigida())
    post.mockRejectedValueOnce(new ApiError('A nova senha precisa ser diferente da atual', 400))
    montar()
    preencherLogin()
    fireEvent.change(await screen.findByLabelText('Nova senha'), {
      target: { value: 'senha-do-papel' },
    })
    fireEvent.change(screen.getByLabelText('Repita a nova senha'), {
      target: { value: 'senha-do-papel' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar e entrar' }))
    expect(
      await screen.findByText('A nova senha precisa ser diferente da atual'),
    ).toBeTruthy()
  })

  it('troca OK + login que falha volta ao login, não repete a troca', async () => {
    // A senha temporária já morreu no servidor: insistir no formulário de
    // troca mandaria a senha velha como "atual" e devolveria 401 para sempre.
    login.mockRejectedValueOnce(trocaExigida())
    post.mockResolvedValue({ success: true })
    login.mockRejectedValueOnce(new Error('Failed to fetch'))
    montar()
    preencherLogin()
    fireEvent.change(await screen.findByLabelText('Nova senha'), {
      target: { value: 'minha-senha-1' },
    })
    fireEvent.change(screen.getByLabelText('Repita a nova senha'), {
      target: { value: 'minha-senha-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar e entrar' }))
    expect(await screen.findByText('Senha alterada. Entre com a sua senha nova.')).toBeTruthy()
    expect(screen.queryByLabelText('Nova senha')).toBeNull()
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeTruthy()
  })

  it('contraprova: credencial errada (401) NÃO abre o formulário de troca', async () => {
    login.mockRejectedValueOnce(new ApiError('Credenciais inválidas', 401))
    montar()
    preencherLogin('errada')
    expect(await screen.findByText('Credenciais inválidas')).toBeTruthy()
    expect(screen.queryByLabelText('Nova senha')).toBeNull()
  })
})


/**
 * A tela da troca é a PRIMEIRA tela do produto para quem chega com a senha no
 * papel — os três acessos novos do RVB começam aqui. Ter saída não basta se a
 * saída parece um erro: o texto que explica o pedido estava com `erroTexto`,
 * o vermelho de NÃO CONFORME (`lk.estado.nc`, negrito), o mesmo da caixa de
 * erro dois elementos abaixo. Nada deu errado; e com os dois vermelhos juntos
 * não dava para saber qual dos dois era o problema.
 *
 * Junto vinham as outras três: nenhuma pista do que o servidor aceita como
 * senha, o botão mudo enquanto grava, e um overlay preto de tela cheia
 * dizendo "ABRINDO LOGIKOS VISION" por cima de uma senha sendo salva — que
 * quando o servidor recusava, virava "abrindo" seguido de erro.
 */
describe('Entrar — a troca obrigatória não pode parecer erro', () => {
  const trocaExigida = () =>
    new ApiError('Sua senha é temporária...', 403, 'password_change_required')

  const abrirTroca = async () => {
    login.mockRejectedValueOnce(trocaExigida())
    montar()
    preencherLogin()
    await screen.findByLabelText('Nova senha')
  }

  it('a explicação é texto de apoio, não o vermelho de não conforme', async () => {
    await abrirTroca()
    const texto = screen.getByText(/A senha que você recebeu é temporária/)
    expect(texto.className).toContain(estilo.textoApoio)
    expect(texto.className).not.toContain(estilo.erroTexto)
  })

  it('diz de qual conta é a senha que está sendo trocada', async () => {
    await abrirTroca()
    expect(screen.getByText('ana@rvb.com.br')).toBeTruthy()
  })

  it('mostra os critérios que o SERVIDOR verifica, e nenhum inventado', async () => {
    await abrirTroca()
    expect(screen.getByText('Mínimo de 6 caracteres')).toBeTruthy()
    expect(screen.getByText('Diferente da senha temporária')).toBeTruthy()
    expect(screen.getByText('As duas digitações coincidem')).toBeTruthy()
    // A prancha pede "letras e números"; o backend NÃO verifica isso
    // (auth/routes.py:264,268-269). Exibir reprovaria senha que ele aceita.
    expect(screen.queryByText(/letras e números/i)).toBeNull()
  })

  it('os critérios acompanham a digitação — · vira ✓ item a item', async () => {
    await abrirTroca()
    const linha = (t: string) => screen.getByText(t).closest('span') as HTMLElement
    expect(linha('Mínimo de 6 caracteres').textContent).toContain('·')

    fireEvent.change(screen.getByLabelText('Nova senha'), { target: { value: 'minha-senha-1' } })
    expect(linha('Mínimo de 6 caracteres').textContent).toContain('✓')
    // A temporária é 'senha-do-papel' (preencherLogin) — já é diferente.
    expect(linha('Diferente da senha temporária').textContent).toContain('✓')
    // Confirmação ainda vazia.
    expect(linha('As duas digitações coincidem').textContent).toContain('·')

    fireEvent.change(screen.getByLabelText('Repita a nova senha'), { target: { value: 'minha-senha-1' } })
    expect(linha('As duas digitações coincidem').textContent).toContain('✓')
  })

  it('repetir a senha temporária aparece como critério não cumprido', async () => {
    await abrirTroca()
    fireEvent.change(screen.getByLabelText('Nova senha'), { target: { value: 'senha-do-papel' } })
    const linha = screen.getByText('Diferente da senha temporária').closest('span') as HTMLElement
    expect(linha.textContent).toContain('·')
  })

  it('enquanto grava, o botão diz "Salvando..." e nada de "ABRINDO LOGIKOS VISION"', async () => {
    await abrirTroca()
    // `post` que não resolve: congela a tela no instante em que a senha está
    // em trânsito, que é justamente o instante que o overlay sequestrava.
    post.mockReturnValueOnce(new Promise(() => {}))
    fireEvent.change(screen.getByLabelText('Nova senha'), { target: { value: 'minha-senha-1' } })
    fireEvent.change(screen.getByLabelText('Repita a nova senha'), { target: { value: 'minha-senha-1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar e entrar' }))

    expect(await screen.findByRole('button', { name: 'Salvando...' })).toBeTruthy()
    expect(screen.queryByText('ABRINDO LOGIKOS VISION')).toBeNull()
    // E o formulário continua visível — a pessoa vê o que mandou.
    expect(screen.getByLabelText('Nova senha')).toBeTruthy()
  })

  it('contraprova: no LOGIN o overlay continua aparecendo', async () => {
    login.mockReturnValueOnce(new Promise(() => {}))
    montar()
    preencherLogin()
    expect(await screen.findByText('ABRINDO LOGIKOS VISION')).toBeTruthy()
  })
})
