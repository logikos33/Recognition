/**
 * `error_code` do backend chegando inteiro no front — e o toast que NÃO deve
 * sair.
 *
 * Por que existe: o envelope de erro já carregava `error_code` há meses
 * (`password_change_required`, `playback_token_expired`, `refresh_not_allowed`),
 * e o front descartava o campo — `ApiError` só guardava `status`. Com isso,
 * "403 porque falta permissão" e "403 porque a senha é temporária" chegavam
 * indistinguíveis na tela de login, que não tinha como oferecer a saída.
 *
 * O toast: 403 em `/auth/login` é sempre a senha temporária. O texto genérico
 * ("Sem permissao para esta acao.") apareceria VERMELHO em cima do formulário
 * de troca, dizendo a coisa errada.
 */
import { waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from './api'
import { useToastStore } from '../components/ui/Toast/useToast'

const resposta = (status: number, corpo: unknown) =>
  Promise.resolve({ ok: false, status, json: () => Promise.resolve(corpo) } as Response)

beforeEach(() => {
  useToastStore.setState({ toasts: [] })
  // `getToken()` lê o localStorage no 1º request do arquivo, quando o do
  // ambiente ainda não responde `getItem` — o erro estourava ANTES de
  // qualquer asserção e o teste passava vazio. Stub explícito: o que este
  // arquivo mede é o envelope de erro, não o armazenamento.
  vi.stubGlobal('localStorage', {
    getItem: () => null, setItem: () => {}, removeItem: () => {},
  })
})

describe('ApiError.code', () => {
  it('carrega o error_code do envelope de erro', async () => {
    vi.stubGlobal('fetch', vi.fn(() => resposta(403, {
      success: false, error: 'senha temporária', error_code: 'password_change_required',
    })))
    const err = await api.post('/auth/login', {}).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(403)
    expect((err as ApiError).code).toBe('password_change_required')
  })

  it('rota sem error_code continua chegando com code undefined', async () => {
    vi.stubGlobal('fetch', vi.fn(() => resposta(500, { success: false, error: 'boom' })))
    const err = await api.get('/qualquer').catch((e) => e)
    expect((err as ApiError).code).toBeUndefined()
    // Espera o toast deste caso ANTES de sair: o `showErrorToast` sai por um
    // import dinâmico e, sem esperar, ele pousava dentro do teste SEGUINTE e
    // reprovava a asserção de "nenhum toast".
    await waitFor(() => expect(useToastStore.getState().toasts.length).toBe(1))
  })

  it('403 do /auth/login não vira toast genérico de "sem permissão"', async () => {
    vi.stubGlobal('fetch', vi.fn(() => resposta(403, {
      success: false, error: 'senha temporária', error_code: 'password_change_required',
    })))
    await api.post('/auth/login', {}).catch(() => {})
    // Espera o mesmo tempo que a contraprova abaixo precisa para o toast
    // aparecer (import dinâmico do errorTranslator) — senão o "não apareceu"
    // seria só "ainda não chegou".
    await new Promise((r) => setTimeout(r, 50))
    expect(useToastStore.getState().toasts).toEqual([])
  })

  it('contraprova: 403 de OUTRA rota continua avisando', async () => {
    vi.stubGlobal('fetch', vi.fn(() => resposta(403, { success: false, error: 'nao pode' })))
    await api.post('/cameras/1/control', {}).catch(() => {})
    await waitFor(() => expect(useToastStore.getState().toasts.length).toBe(1))
  })
})
