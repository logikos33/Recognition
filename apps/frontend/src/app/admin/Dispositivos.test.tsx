/**
 * O que esta tela não pode errar:
 *
 *  · POST vai para `/devices/claim-codes` — SEM `/v1` (o blueprint real usa
 *    `url_prefix="/api/devices"`, não `/api/v1/devices`).
 *  · o código só aparece DEPOIS de gerar, e NUNCA reaparece sozinho: um
 *    remount (sair da tela e voltar) tem de renderizar limpo — se alguém
 *    "otimizar" isso guardando o código fora do componente (module-level,
 *    localStorage), este teste quebra.
 *  · a seção de listagem/revogação do desenho — sem rota no backend — não
 *    inventa linha nem rótulo vazio: mostra a nota de omissão, só isso.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const post = vi.fn()
vi.mock('../../services/api', () => ({
  api: { post: (...a: unknown[]) => post(...a) },
}))

const toastErro = vi.fn()
vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: toastErro, warning: vi.fn(), info: vi.fn() }),
}))

import { Dispositivos } from './Dispositivos'

const CLAIM_REAL = {
  claim_code: 'ABCD2345',
  claim_id: 'c1',
  expires_at: '2026-08-29T15:00:00Z',
  expires_in_minutes: 15,
}

beforeEach(() => {
  post.mockReset()
  toastErro.mockReset()
})

describe('Dispositivos', () => {
  it('gerar código chama POST /devices/claim-codes (sem /v1) e mostra o código uma vez', async () => {
    post.mockResolvedValue({ status: 'success', data: CLAIM_REAL })
    render(<Dispositivos />)

    expect(screen.queryByText('ABCD2345')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Gerar código de reivindicação' }))

    expect(await screen.findByText('ABCD2345')).toBeTruthy()
    expect(screen.getByText('EXPIRA EM 15 MIN')).toBeTruthy()
    expect(post).toHaveBeenCalledWith('/devices/claim-codes')
  })

  it('mutação: código NÃO reaparece sozinho num remount — estado é só local', async () => {
    post.mockResolvedValue({ status: 'success', data: CLAIM_REAL })
    const { unmount } = render(<Dispositivos />)
    fireEvent.click(screen.getByRole('button', { name: 'Gerar código de reivindicação' }))
    expect(await screen.findByText('ABCD2345')).toBeTruthy()

    unmount()
    render(<Dispositivos />)
    expect(screen.queryByText('ABCD2345')).toBeNull()
  })

  it('erro ao gerar → toast de erro, sem código na tela', async () => {
    post.mockRejectedValue(new Error('Apenas administradores podem gerar claim codes'))
    render(<Dispositivos />)

    fireEvent.click(screen.getByRole('button', { name: 'Gerar código de reivindicação' }))

    await vi.waitFor(() => expect(toastErro).toHaveBeenCalledWith('Apenas administradores podem gerar claim codes'))
    expect(screen.queryByText(/EXPIRA EM/)).toBeNull()
  })

  it('seção sem fonte (listagem/revogação) some — só a nota de omissão aparece, nunca rótulo vazio', () => {
    render(<Dispositivos />)
    expect(screen.queryByText('Revogar')).toBeNull()
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.getByText(/ainda não têm rota no backend/)).toBeTruthy()
  })
})
