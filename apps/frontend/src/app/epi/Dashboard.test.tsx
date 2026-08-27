/**
 * O que este dashboard não pode fazer, e é o que se trava aqui:
 *
 *  · **inventar número.** Score sem cálculo possível vira "—", nunca 100; ação
 *    sem endpoint vira "Indisponível", nunca "6 abertas". Um dashboard de
 *    segurança que preenche lacuna com número plausível é pior que um vazio:
 *    o gestor age em cima do que leu.
 *  · **mostrar cor sozinha.** Todo estado sai com palavra junto — quem não
 *    distingue verde de vermelho ainda tem de conseguir operar.
 *  · **oferecer link que dá 403.** "triar eventos" e "ver saúde" só aparecem
 *    para quem tem a permissão da tela de destino (`navPorPerfil` já provou
 *    que item que leva a porta fechada é pior que item ausente).
 *  · **chamar "sem dados" um dia bom.** Zero evento com câmera rodando é o
 *    resultado que o cliente quer — esconder isso atrás do estado vazio
 *    apagaria justamente o dia em que ninguém se machucou.
 *  · **mentir sobre o alcance do filtro.** O turno recorta os painéis de
 *    evento; os KPIs do topo o backend fixa em "hoje"/"24 h", e a tela diz.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Dashboard } from './Dashboard'

const getStats = vi.fn()
const getTimeline = vi.fn()
const getSummary = vi.fn()

vi.mock('../../services/moduleService', () => ({
  moduleService: { getStats: (...a: unknown[]) => getStats(...a) },
}))
vi.mock('../../services/eventsService', () => ({
  eventsService: {
    getTimeline: (...a: unknown[]) => getTimeline(...a),
    getSummary: (...a: unknown[]) => getSummary(...a),
  },
}))

/**
 * Node 25 traz Web Storage nativo e ele colide com o do jsdom neste ambiente
 * (mesmo achado já registrado em `tenantContextRenewal.test.ts`) — o global
 * real perde métodos. Storage in-memory resolve, e de quebra isola a
 * preferência de widgets entre casos.
 */
class MemoriaStorage implements Storage {
  private mapa = new Map<string, string>()
  get length(): number { return this.mapa.size }
  clear(): void { this.mapa.clear() }
  getItem(k: string): string | null { return this.mapa.get(k) ?? null }
  key(i: number): string | null { return Array.from(this.mapa.keys())[i] ?? null }
  removeItem(k: string): void { this.mapa.delete(k) }
  setItem(k: string, v: string): void { this.mapa.set(k, String(v)) }
}

/** Formato real de `module_service.get_stats` (RVB — 3 câmeras, 1 fora). */
const STATS_RVB = {
  cameras_active: 2,
  cameras_total: 3,
  alerts_today: 23,
  alerts_week: 196, // média 7d = 28 → −18%, o número do desenho
  compliance_rate: 87,
}

function montar({
  permissoes = ['alerts:read', 'cameras:read'],
}: { permissoes?: string[] } = {}) {
  localStorage.setItem(
    'user',
    JSON.stringify({ id: 'u1', email: 'a@b.c', name: 'Ana', role: 'operator', permissions: permissoes }),
  )
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoriaStorage())
  getStats.mockResolvedValue({ ...STATS_RVB })
  getTimeline.mockResolvedValue({ bucket: 'hour', timeline: [] })
  getSummary.mockResolvedValue({ total: 0, by_class: [], by_camera: [] })
})

afterEach(() => vi.clearAllMocks())

describe('EPI Dashboard — números', () => {
  it('mostra o score da API e não um número de exemplo', async () => {
    montar()
    expect(await screen.findByText('87')).toBeTruthy()
    // O 82 do protótipo ("+5 vs ontem") não pode vazar para a tela.
    expect(screen.queryByText(/vs ontem/i)).toBeNull()
  })

  it('score sem cálculo possível vira "—" e a palavra Indisponível, nunca 100', async () => {
    getStats.mockResolvedValue({ ...STATS_RVB, cameras_active: 0, compliance_rate: null })
    montar()
    const cartao = await screen.findByLabelText('Score de conformidade')
    expect(within(cartao).getByText('—')).toBeTruthy()
    expect(within(cartao).getByText('Indisponível')).toBeTruthy()
    expect(within(cartao).queryByText('100')).toBeNull()
  })

  it('declara que não tem histórico de 7 dias em vez de desenhar uma curva', async () => {
    montar()
    expect(await screen.findByText(/SEM HISTÓRICO · 7 DIAS/)).toBeTruthy()
  })

  it('deriva o delta de eventos da média de 7 dias que a API devolveu', async () => {
    montar()
    const cartao = await screen.findByLabelText('Eventos hoje')
    expect(within(cartao).getByText('23')).toBeTruthy()
    // 23 vs média 28 (196/7) = −18%
    expect(within(cartao).getByText(/−18% vs média 7d/)).toBeTruthy()
  })

  it('sem semana nenhuma, admite que não há média — não escreve 0%', async () => {
    getStats.mockResolvedValue({ ...STATS_RVB, alerts_week: 0, alerts_today: 0 })
    montar()
    const cartao = await screen.findByLabelText('Eventos hoje')
    expect(within(cartao).getByText(/sem média de 7 dias ainda/)).toBeTruthy()
  })
})

describe('EPI Dashboard — o que o backend não tem', () => {
  it('ações aparecem como indisponíveis, sem número inventado', async () => {
    montar()
    const cartao = await screen.findByLabelText('Ações abertas')
    expect(within(cartao).getByText('—')).toBeTruthy()
    expect(within(cartao).getByText('Indisponível')).toBeTruthy()
    // Os exemplos do protótipo não podem aparecer como se fossem dado.
    expect(screen.queryByText(/Reforçar DDS na doca/i)).toBeNull()
    expect(screen.queryByText(/CARLOS M\./i)).toBeNull()
  })

  it('não oferece seletor de site — nenhum endpoint desta tela aceita site', async () => {
    montar()
    await screen.findByText('87')
    expect(screen.queryByLabelText(/site/i)).toBeNull()
  })
})

describe('EPI Dashboard — estado é cor + ícone + palavra', () => {
  it('câmera fora do ar sai com a palavra, não só com âmbar', async () => {
    montar()
    const cartao = await screen.findByLabelText('Câmeras online')
    expect(within(cartao).getByText('1 fora do ar')).toBeTruthy()
  })

  it('frota inteira de pé diz "Todas online"', async () => {
    getStats.mockResolvedValue({ ...STATS_RVB, cameras_active: 3 })
    montar()
    const cartao = await screen.findByLabelText('Câmeras online')
    expect(within(cartao).getByText('Todas online')).toBeTruthy()
  })
})

describe('EPI Dashboard — permissão', () => {
  it('esconde os atalhos das telas que o perfil não pode abrir', async () => {
    montar({ permissoes: [] })
    await screen.findByText('87')
    expect(screen.queryByText(/triar eventos/)).toBeNull()
    expect(screen.queryByText(/ver saúde/)).toBeNull()
  })

  it('mostra os atalhos para quem pode', async () => {
    montar()
    expect(await screen.findByText(/triar eventos/)).toBeTruthy()
    expect(screen.getByText(/ver saúde/)).toBeTruthy()
  })
})

describe('EPI Dashboard — vazio, erro e turno', () => {
  it('dia sem violação NÃO é tela vazia: mostra o score e zero eventos', async () => {
    getStats.mockResolvedValue({
      cameras_active: 3, cameras_total: 3, alerts_today: 0, alerts_week: 0, compliance_rate: 100,
    })
    montar()
    expect(await screen.findByText('100')).toBeTruthy()
    expect(screen.queryByText(/Sem dados para este módulo/)).toBeNull()
  })

  it('sem câmera e sem evento, aí sim é vazio — com caminho de saída', async () => {
    getStats.mockResolvedValue({
      cameras_active: 0, cameras_total: 0, alerts_today: 0, alerts_week: 0, compliance_rate: null,
    })
    montar()
    expect(await screen.findByText(/Sem dados para este módulo/)).toBeTruthy()
    expect(screen.getByText('Ver câmeras')).toBeTruthy()
  })

  it('falha de carga mostra a rota que falhou e um retry que refaz a chamada', async () => {
    getStats.mockRejectedValue(new Error('timeout'))
    montar()
    expect(await screen.findByText(/Não foi possível carregar/)).toBeTruthy()
    expect(screen.getByText(/GET \/API\/MODULES\/EPI\/STATS/)).toBeTruthy()

    getStats.mockResolvedValue({ ...STATS_RVB })
    fireEvent.click(screen.getByText('Tentar novamente'))
    expect(await screen.findByText('87')).toBeTruthy()
  })

  it('trocar o turno reconsulta os eventos na janela nova', async () => {
    montar()
    await screen.findByText('87')
    await waitFor(() => expect(getTimeline).toHaveBeenCalled())

    const primeira = getTimeline.mock.calls.at(-1)?.[0] as { from: string; to: string }
    fireEvent.change(screen.getByLabelText('Turno'), { target: { value: 'primeiro' } })

    await waitFor(() => {
      const ultima = getTimeline.mock.calls.at(-1)?.[0] as { from: string; to: string }
      expect(ultima.from).not.toBe(primeira.from)
    })
    const ultima = getTimeline.mock.calls.at(-1)?.[0] as { from: string; to: string }
    expect(new Date(ultima.from).getHours()).toBe(6)
    expect(new Date(ultima.to).getHours()).toBe(14)
  })
})

describe('EPI Dashboard — painéis', () => {
  it('período sem evento diz que está sem evento, não desenha barra', async () => {
    montar()
    const painel = await screen.findByLabelText('Eventos por hora')
    expect(within(painel).getByText('Sem eventos no período.')).toBeTruthy()
  })

  it('violações por classe saem do resumo da API, com o percentual real', async () => {
    getSummary.mockResolvedValue({
      total: 23,
      by_class: [
        { class: 'no_helmet', count: 12 },
        { class: 'no_vest', count: 6 },
        { class: 'no_gloves', count: 5 },
      ],
      by_camera: [],
    })
    montar()
    const painel = await screen.findByLabelText('Violações por classe')
    expect(within(painel).getByText('Sem capacete')).toBeTruthy()
    expect(within(painel).getByText('12')).toBeTruthy()
    // 12 de 23 = 52%, o mesmo número do desenho — só que calculado.
    expect(within(painel).getByText(/concentra 52% das violações/)).toBeTruthy()
  })

  it('esconder um widget o tira da tela e a preferência sobrevive à remontagem', async () => {
    // `region` = o <section> do painel. O checkbox do popover carrega o mesmo
    // rótulo, e por nome só a busca pegaria os dois.
    const painelAcoes = () => screen.queryByRole('region', { name: 'Ações recentes' })

    const tela = montar()
    await screen.findByText('87')
    expect(painelAcoes()).toBeTruthy()

    fireEvent.click(screen.getByText('Personalizar widgets'))
    fireEvent.click(await screen.findByLabelText('Ações recentes', { selector: 'input' }))
    await waitFor(() => expect(painelAcoes()).toBeNull())

    tela.unmount()
    montar()
    await screen.findByText('87')
    expect(painelAcoes()).toBeNull()
  })
})
