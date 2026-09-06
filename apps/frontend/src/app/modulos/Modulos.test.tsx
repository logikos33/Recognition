/**
 * O que esta tela não pode errar: mandar a pessoa para o módulo errado, pedir
 * escolha quando não há escolha, e inventar pendência que o backend não serve.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ user: { name: 'Ana Ribeiro', role: 'admin' }, isSuperAdmin: false }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

const get = vi.fn()
vi.mock('../../services/api', () => ({ api: { get: (...a: unknown[]) => get(...a) } }))

const navegar = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => navegar,
}))

import { Modulos } from './Modulos'

/** O envelope REAL de GET /api/modules/, medido no DEV em 29/08. */
const resposta = (mods: Array<Record<string, unknown>>) => ({
  success: true,
  message: 'OK',
  data: { modules: mods },
})
const mod = (module_code: string, extra: Record<string, unknown> = {}) => ({
  module_code,
  enabled: true,
  alerts_today: 0,
  cameras_count: 0,
  ...extra,
})

const montar = () => render(<MemoryRouter><Modulos /></MemoryRouter>)

/**
 * O jsdom desta configuração expõe um `localStorage` OCO — o objeto existe, os
 * métodos não. O componente sobrevive a isso (o selo de última visita
 * simplesmente não aparece, que é o comportamento correto num navegador sem
 * armazenamento), mas para PROVAR o selo é preciso dar a capacidade que um
 * navegador de verdade tem.
 */
function armazenamentoDeMentira() {
  const mapa = new Map<string, string>()
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => mapa.get(k) ?? null,
      setItem: (k: string, v: string) => void mapa.set(k, v),
      removeItem: (k: string) => void mapa.delete(k),
      clear: () => mapa.clear(),
    },
  })
}

beforeEach(() => {
  get.mockReset()
  navegar.mockReset()
  auth.isSuperAdmin = false
  armazenamentoDeMentira()
})

describe('escolha de módulo', () => {
  it('só lista módulo que TEM tela — código sem destino não vira cartão', async () => {
    // `basic` e `analytics` existem no backend e não têm tela em lugar nenhum.
    // Cartão que não leva a lugar nenhum é pior que ausência.
    get.mockResolvedValue(resposta([mod('epi'), mod('quality'), mod('basic'), mod('analytics')]))
    montar()
    await screen.findByText('EPI · Segurança')
    expect(screen.getByText('Qualidade')).toBeTruthy()
    expect(screen.queryByText(/basic|analytics/i)).toBeNull()
  })

  it('com UM módulo só, entra direto — não pede escolha de uma opção', async () => {
    // É o caso do RVB hoje: só EPI. E é a regra escrita no rodapé do desenho.
    get.mockResolvedValue(resposta([mod('epi')]))
    montar()
    await waitFor(() =>
      expect(navegar).toHaveBeenCalledWith('/novo/epi/dashboard', { replace: true }),
    )
    expect(screen.queryByText(/onde você vai trabalhar/i)).toBeNull()
  })

  it('a tecla do número abre o módulo daquela posição', async () => {
    get.mockResolvedValue(resposta([mod('epi'), mod('quality')]))
    montar()
    await screen.findByText('EPI · Segurança')
    // findByText só prova que o CARTÃO renderizou. O listener de teclado é
    // re-registrado por um useEffect separado (deps `[cartoes, abrir]`) — sob
    // contenção de CPU o keydown pode chegar antes desse efeito recomeçar
    // ouvindo com a lista carregada, e cair no listener velho (cartoes=[]),
    // que ignora a tecla. act() esvazia o efeito pendente antes do evento.
    await act(async () => {})
    fireEvent.keyDown(window, { key: '1' })
    expect(navegar).toHaveBeenCalledWith('/novo/epi/dashboard')
  })

  it('mostra alerts_today de verdade, e diz quando é zero', async () => {
    // O desenho traz pendências por módulo ("3 NOK aguardam revisão") que o
    // backend NÃO serve. A única real é alerts_today.
    get.mockResolvedValue(resposta([mod('epi', { alerts_today: 4 }), mod('quality')]))
    montar()
    expect(await screen.findByText('4 alertas hoje')).toBeTruthy()
    expect(screen.getByText('sem alertas hoje')).toBeTruthy()
    // e nada inventado
    expect(screen.queryByText(/NOK aguardam|divergências a validar|propostas para aprovar/i))
      .toBeNull()
  })

  it('sem módulo habilitado, diz isso — não fica em branco', async () => {
    get.mockResolvedValue(resposta([]))
    montar()
    expect(await screen.findByText(/nenhum módulo liberado/i)).toBeTruthy()
  })

  it('erro mostra o motivo e o retry refaz a chamada', async () => {
    get.mockRejectedValueOnce(new Error('boom')).mockResolvedValue(resposta([mod('epi'), mod('quality')]))
    montar()
    expect(await screen.findByText('boom')).toBeTruthy()
    expect(screen.queryByText(/GET \/api/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    await screen.findByText('EPI · Segurança')
  })

  it('o selo de última visita só aparece depois de haver visita', async () => {
    // Não há endpoint para isso; guardamos no navegador de quem usa. Sem
    // registro, o selo não existe — nunca uma data inventada.
    get.mockResolvedValue(resposta([mod('epi'), mod('quality')]))
    const { unmount } = montar()
    await screen.findByText('EPI · Segurança')
    expect(screen.queryByText(/ÚLTIMA VISITA/)).toBeNull()

    // Mesma corrida da tecla do número acima: sem o flush, o keydown pode
    // cair no listener velho e `registrarVisita` nunca roda — o selo do
    // remount seguinte ficaria sempre ausente, não só "às vezes".
    await act(async () => {})
    fireEvent.keyDown(window, { key: '1' })
    unmount()
    montar()
    expect(await screen.findByText(/ÚLTIMA VISITA · HOJE/)).toBeTruthy()
  })

  it('o atalho de admin só existe para superadmin', async () => {
    get.mockResolvedValue(resposta([mod('epi'), mod('quality')]))
    const { unmount } = montar()
    await screen.findByText('EPI · Segurança')
    expect(screen.queryByText(/painel admin/i)).toBeNull()
    unmount()

    auth.isSuperAdmin = true
    montar()
    expect(await screen.findByText(/painel admin/i)).toBeTruthy()
  })
})
