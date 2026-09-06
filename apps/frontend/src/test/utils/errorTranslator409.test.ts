/**
 * 409 em `/verification` não é erro do operador — e não pode sair como toast
 * vermelho automático do `api.ts` (issue #675).
 *
 * O backend recusa o SEGUNDO veredito sobre o mesmo alerta e responde 409 com
 * QUEM julgou e QUANDO. As cinco telas que chamam `POST
 * /verification/<id>/review` mostram essa frase no seu próprio aviso
 * informativo. Sem a regra silenciosa, `showErrorToast` disparava ANTES, e o
 * operador via dois avisos para o mesmo fato — sendo o primeiro vermelho,
 * dizendo que deu erro o que na verdade é informação.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { showErrorToast } from '../../utils/errorTranslator'
import { useToastStore } from '../../components/ui/Toast/useToast'

beforeEach(() => useToastStore.setState({ toasts: [] }))

const toasts = () => useToastStore.getState().toasts

describe('toast automático do api.ts', () => {
  it('cala no 409 de /verification — quem informa é a tela', () => {
    showErrorToast(409, '/verification/abc-123/review', 'Maria já avaliou este alerta')
    expect(toasts()).toHaveLength(0)
  })

  it('não cala 409 de OUTRAS rotas (a regra é do veredito, não do status)', () => {
    showErrorToast(409, '/cameras/abc-123', 'conflito')
    expect(toasts()).toHaveLength(1)
  })

  it('não cala outros erros de /verification (500 continua vermelho)', () => {
    showErrorToast(500, '/verification/abc-123/review', 'boom')
    expect(toasts()).toHaveLength(1)
    expect(toasts()[0].variant).toBe('error')
  })

  // Mesma regra, outra rota: a troca de senha obrigatória (#819). A prova de
  // que ela vale no caminho REAL está em `Entrar.travessia.test.tsx`; aqui
  // ficam os limites, para a regra não virar mordaça.
  it('cala o 400 de /auth/change-password — a frase já está na caixa da tela', () => {
    showErrorToast(400, '/auth/change-password', 'A nova senha precisa ser diferente da atual')
    expect(toasts()).toHaveLength(0)
  })

  it('cala o 429 de /auth/change-password (limite por conta, também mostrado na tela)', () => {
    showErrorToast(429, '/auth/change-password', 'Muitas tentativas de login.')
    expect(toasts()).toHaveLength(0)
  })

  it('NÃO cala o 500 de /auth/change-password — aí não é dado ruim, é o sistema', () => {
    showErrorToast(500, '/auth/change-password', 'Erro interno')
    expect(toasts()).toHaveLength(1)
  })

  it('NÃO cala 400 de outras rotas (a regra é da troca de senha, não do status)', () => {
    showErrorToast(400, '/cameras', 'campo obrigatório')
    expect(toasts()).toHaveLength(1)
  })
})
