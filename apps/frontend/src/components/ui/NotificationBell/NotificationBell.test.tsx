/**
 * NotificationBell — ux2/dedup.
 *
 * Achado do Vitor: "10 pendentes", todas a MESMA cena de 6 dias atrás (Entrada
 * Expedição · Sem máscara/Sem Luvas · há 6d). Um badge que conta linhas em vez
 * de situações mente sobre quanto trabalho existe — e "clicar na notificação
 * TEM de levar ao evento" (deep-link) já funcionava antes desta rodada; estes
 * testes travam que continua funcionando depois de agrupar.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn()
vi.mock('../../../services/api', () => ({ api: { get: (...a: unknown[]) => get(...a) } }))

const navigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<Record<string, unknown>>('react-router-dom')
  return { ...real, useNavigate: () => navigate }
})

import { NotificationBell } from './NotificationBell'

const alerta = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  camera_id: 'cam-expedicao',
  camera_name: 'Entrada Expedição',
  violations: [{ class: 'no_helmet', confidence: 0.9 }],
  acknowledged: false,
  created_at: '2026-08-25T13:39:00Z',
  ...extra,
})

function montar(props: { rotaAlertas?: string } = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <NotificationBell {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function abrirPainel() {
  const botao = await screen.findByLabelText('Notificações')
  botao.click()
}

beforeEach(() => {
  get.mockReset()
  navigate.mockReset()
})

describe('deep-link continua valendo (não regrediu ao agrupar)', () => {
  it('clicar num alerta sem irmãos leva ao evento com highlight', async () => {
    get.mockResolvedValue({ data: { alerts: [alerta('a1')], total: 1, total_situacoes: 1 } })
    montar()
    await abrirPainel()
    const cartao = await screen.findByRole('button', { name: /Entrada Expedição/ })
    cartao.click()
    expect(navigate).toHaveBeenCalledWith(
      '/epi/alerts?camera_id=cam-expedicao&acknowledged=false&kind=violation&highlight=a1',
    )
  })
})

describe('rajada (ux2/dedup) — badge e painel contam SITUAÇÕES, não linhas', () => {
  it('10 alertas da MESMA câmera+classe em <60s viram 1 situação no badge', async () => {
    const dez = Array.from({ length: 10 }, (_, i) =>
      alerta(`r${i}`, { created_at: new Date(Date.parse('2026-08-25T13:39:00Z') + i * 2000).toISOString() }),
    )
    get.mockResolvedValue({ data: { alerts: dez, total: 10, total_situacoes: 1 } })
    montar()
    await waitFor(() => expect(screen.getByLabelText('Notificações').textContent).toContain('1'))
    await abrirPainel()
    await screen.findByText('1 pendente')
  })

  it('painel mostra 1 cartão representante + alternador "+9 repetições" — nunca 10 cartões idênticos', async () => {
    const dez = Array.from({ length: 10 }, (_, i) =>
      alerta(`r${i}`, { created_at: new Date(Date.parse('2026-08-25T13:39:00Z') + i * 2000).toISOString() }),
    )
    get.mockResolvedValue({ data: { alerts: dez, total: 10, total_situacoes: 1 } })
    montar()
    await abrirPainel()
    expect(await screen.findAllByRole('button', { name: /Entrada Expedição/ })).toHaveLength(1)
    await screen.findByText(/\+9 repetiç/)
  })

  it('expandir revela as N repetições, e cada uma mantém o PRÓPRIO deep-link', async () => {
    const tres = [
      alerta('x1', { created_at: '2026-08-25T13:39:00Z' }),
      alerta('x2', { created_at: '2026-08-25T13:39:10Z' }),
      alerta('x3', { created_at: '2026-08-25T13:39:20Z' }),
    ]
    get.mockResolvedValue({ data: { alerts: tres, total: 3, total_situacoes: 1 } })
    montar()
    await abrirPainel()
    const alternador = await screen.findByText(/\+2 repetiç/)
    alternador.click()
    // As duas repetições (x1, x2 — x3 é o representante mais recente) viram
    // botões clicáveis próprios, não texto morto escondido. O aria-label da
    // repetição usa "·" (o do representante usa ":") — separa os dois grupos.
    const botoesRepeticao = await screen.findAllByRole('button', { name: /Abrir alerta de Entrada Expedição ·/ })
    expect(botoesRepeticao).toHaveLength(2)
    botoesRepeticao[0].click()
    expect(navigate).toHaveBeenCalledWith(expect.stringContaining('highlight=x1'))
  })

  it('sem total_situacoes no payload (backend/mock antigo), o badge cai pro nº de linhas — como sempre foi', async () => {
    get.mockResolvedValue({ data: { alerts: [alerta('y1'), alerta('y2', { camera_id: 'outra-cam' })], total: 2 } })
    montar()
    await waitFor(() => expect(screen.getByLabelText('Notificações').textContent).toContain('2'))
  })
})


/**
 * O front NOVO monta ESTE sino (Shell.tsx). `/epi/alerts` é rota VÁLIDA no app:
 * sem `rotaAlertas`, o sino do front novo jogaria o usuário, calado, na tela
 * ANTIGA — o mesmo pisão que `RotasNovas.tsx` descreve (aconteceu em 10 lugares
 * na primeira leva, e nenhum teste pegou).
 */
describe('deep-link segue o front que montou o sino', () => {
  it('sem prop, continua no endereço do front antigo (TopBar legada)', async () => {
    get.mockResolvedValue({ data: { alerts: [alerta('a1')], total: 1, total_situacoes: 1 } })
    montar()
    await abrirPainel()
    ;(await screen.findByRole('button', { name: /Entrada Expedição/ })).click()
    expect(navigate).toHaveBeenCalledWith(expect.stringContaining('/epi/alerts?'))
  })

  it('com rotaAlertas, cartão E "Ver todos" vão para a tela do front novo', async () => {
    get.mockResolvedValue({ data: { alerts: [alerta('a1')], total: 1, total_situacoes: 1 } })
    montar({ rotaAlertas: '/novo/epi/eventos' })
    await abrirPainel()
    ;(await screen.findByRole('button', { name: /Entrada Expedição/ })).click()
    expect(navigate).toHaveBeenCalledWith(
      '/novo/epi/eventos?camera_id=cam-expedicao&acknowledged=false&kind=violation&highlight=a1',
    )
    await abrirPainel()
    ;(await screen.findByRole('button', { name: /Ver todos os alertas/ })).click()
    expect(navigate).toHaveBeenCalledWith('/novo/epi/eventos?acknowledged=false&kind=violation')
  })
})
