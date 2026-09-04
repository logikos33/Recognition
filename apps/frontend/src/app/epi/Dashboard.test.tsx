/**
 * O que este dashboard não pode fazer, e é o que se trava aqui:
 *
 *  · **inventar número.** Score sem cálculo possível vira "—", nunca 100; ação
 *    sem endpoint vira "Indisponível", nunca "6 abertas". Um dashboard de
 *    segurança que preenche lacuna com número plausível é pior que um vazio:
 *    o gestor age em cima do que leu.
 *  · **mostrar cor sozinha.** Todo estado sai com palavra junto — quem não
 *    distingue verde de vermelho ainda tem de conseguir operar.
 *  · **oferecer link que dá 403.** "triar eventos" e "ver câmeras" só aparecem
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
const getProfile = vi.fn()

vi.mock('../../services/moduleService', () => ({
  moduleService: { getStats: (...a: unknown[]) => getStats(...a) },
}))
vi.mock('../../services/eventsService', () => ({
  eventsService: {
    getTimeline: (...a: unknown[]) => getTimeline(...a),
    getSummary: (...a: unknown[]) => getSummary(...a),
    getProfile: (...a: unknown[]) => getProfile(...a),
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

/** Vazio de `/events/profile` — nenhum evento capturado na janela. */
const PERFIL_VAZIO = {
  rows: [],
  situacao: {
    total: 0,
    nao_reconhecidos: 0,
    procedentes: 0,
    improcedentes: 0,
    cameras: 0,
    primeira_captura: null,
    ultima_captura: null,
    confianca_media: null,
  },
}

/**
 * Perfil com os números REAIS medidos no DEV (RVB, 423 alertas): 302
 * conformidade, 66 violação, 55 não definida — a proporção importa, porque é
 * ela que prova que "423 alertas" não é "423 violações".
 */
const PERFIL_RVB = {
  rows: [
    { bucket: '2026-08-21T13:00:00', kind: 'violacao', count: 40 },
    { bucket: '2026-08-21T13:00:00', kind: 'conformidade', count: 97 },
    { bucket: '2026-08-21T17:00:00', kind: 'violacao', count: 26 },
    { bucket: '2026-08-21T17:00:00', kind: 'conformidade', count: 205 },
    { bucket: '2026-08-23T13:00:00', kind: 'indefinido', count: 55 },
  ],
  situacao: {
    total: 423,
    nao_reconhecidos: 396,
    procedentes: 60,
    improcedentes: 62,
    cameras: 14,
    primeira_captura: '2026-08-21T10:30:00',
    ultima_captura: '2026-08-23T13:41:30',
    confianca_media: 0.5622104018912525,
  },
}

beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoriaStorage())
  getStats.mockResolvedValue({ ...STATS_RVB })
  getTimeline.mockResolvedValue({ bucket: 'hour', timeline: [] })
  getSummary.mockResolvedValue({ total: 0, by_class: [], by_camera: [] })
  getProfile.mockResolvedValue(PERFIL_VAZIO)
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
    expect(await screen.findByText(/SCORE SEM SÉRIE · 7 DIAS/)).toBeTruthy()
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
  it('não sobra cartão morto na tela: o travessão de "Ações abertas" saiu', async () => {
    getProfile.mockResolvedValue(PERFIL_RVB)
    montar()
    await screen.findByText('87')
    // O cartão inventava um domínio (ação corretiva com prazo e responsável)
    // que não existe em tabela nenhuma, e ocupava um quarto da faixa de KPI
    // com um "—". Espaço de tela não se gasta com placeholder.
    expect(screen.queryByLabelText('Ações abertas')).toBeNull()
    expect(screen.queryByText('Indisponível')).toBeNull()
    // Os exemplos do protótipo continuam banidos.
    expect(screen.queryByText(/Reforçar DDS na doca/i)).toBeNull()
    expect(screen.queryByText(/CARLOS M\./i)).toBeNull()
  })

  it('não oferece seletor de site — nenhum endpoint desta tela aceita site', async () => {
    montar()
    await screen.findByText('87')
    expect(screen.queryByLabelText(/site/i)).toBeNull()
  })
})

describe('EPI Dashboard — câmeras não fingem telemetria que não existe (D1)', () => {
  it('mostra só o número de câmeras ativas — nunca "online", que prometeria conectividade não medida', async () => {
    montar()
    const cartao = await screen.findByLabelText('Câmeras ativas')
    const valor = within(cartao).getByText('2')
    expect(valor).toBeTruthy()
    // getByText('2') casa igual com "2/3": por padrão o testing-library só
    // junta os text nodes DIRETOS do elemento, então um <span> aninhado com
    // o "/3" fica fora do match e passaria despercebido. .textContent pega
    // a árvore inteira — é o que de fato trava a fração fora da tela.
    expect(valor.textContent).toBe('2')
    expect(within(cartao).getByText('Cadastradas e ativas')).toBeTruthy()
    expect(within(cartao).queryByText(/online/i)).toBeNull()
    expect(within(cartao).queryByText(/fora do ar/i)).toBeNull()
  })

  it('zero câmera ativa admite isso em vez de inventar contagem', async () => {
    getStats.mockResolvedValue({ ...STATS_RVB, cameras_active: 0, cameras_total: 0 })
    montar()
    const cartao = await screen.findByLabelText('Câmeras ativas')
    const valor = within(cartao).getByText('0')
    expect(valor.textContent).toBe('0')
    expect(within(cartao).getByText('Nenhuma câmera ativa')).toBeTruthy()
  })
})

describe('EPI Dashboard — permissão', () => {
  it('esconde os atalhos das telas que o perfil não pode abrir', async () => {
    montar({ permissoes: [] })
    await screen.findByText('87')
    expect(screen.queryByText(/triar eventos/)).toBeNull()
    expect(screen.queryByText(/ver câmeras/)).toBeNull()
  })

  it('mostra os atalhos para quem pode', async () => {
    montar()
    expect(await screen.findByText(/triar eventos/)).toBeTruthy()
    expect(screen.getByText(/ver câmeras/)).toBeTruthy()
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

  it('ranking de câmeras: só as 3 primeiras saem em destaque, resto neutro', async () => {
    getSummary.mockResolvedValue({
      total: 0,
      by_class: [],
      by_camera: [
        { camera_id: 'c1', camera_name: 'Entrada Expedição', count: 108 },
        { camera_id: 'c2', camera_name: 'Guarita', count: 63 },
        { camera_id: 'c3', camera_name: 'Porta Pallets', count: 41 },
        { camera_id: 'c4', camera_name: 'Manutenção', count: 28 },
      ],
    })
    montar()
    const painel = await screen.findByLabelText('Câmeras com mais eventos')
    // Posições são sempre zero-padded ("01".."04") — só elas batem este padrão,
    // nunca as contagens (108/63/41/28), que não começam com zero.
    const posicoes = within(painel).getAllByText(/^0[1-9]$/)
    expect(posicoes).toHaveLength(4)

    const nomeTop = within(painel).getByText('Entrada Expedição')
    const nomeResto = within(painel).getByText('Manutenção')
    expect(nomeTop.className).not.toBe(nomeResto.className)

    // Backend já devolve top-10 ordenado por count DESC (top_cameras_by_alerts).
    // 108 + 63 + 41 = 212 de 240 no total = 88%.
    expect(within(painel).getByText('88%')).toBeTruthy()
  })

  it('ranking de câmeras vazio diz que não há eventos, não desenha barra nenhuma', async () => {
    getSummary.mockResolvedValue({ total: 0, by_class: [], by_camera: [] })
    montar()
    const painel = await screen.findByLabelText('Câmeras com mais eventos')
    expect(within(painel).getByText('Sem eventos no período')).toBeTruthy()
  })

  it('câmera sem nome não vaza UUID cru na tela', async () => {
    getSummary.mockResolvedValue({
      total: 0,
      by_class: [],
      by_camera: [{ camera_id: 'c1', camera_name: null, count: 5 }],
    })
    montar()
    const painel = await screen.findByLabelText('Câmeras com mais eventos')
    expect(within(painel).getByText('Sem nome')).toBeTruthy()
  })

  it('barra de eventos por hora leva pra lista filtrada naquela hora exata', async () => {
    // Hora corrente truncada em UTC: sempre cai dentro do turno padrão
    // ("dia", 00h–24h local), sem depender de fuso ou de quando o teste roda.
    const inicioHora = new Date()
    inicioHora.setUTCMinutes(0, 0, 0)
    const bucketIso = inicioHora.toISOString()
    getTimeline.mockResolvedValue({ bucket: 'hour', timeline: [{ bucket: bucketIso, count: 4 }] })
    montar()
    const painel = await screen.findByLabelText('Eventos por hora')
    const barra = within(painel).getByTitle(/4 evento/)
    expect(barra.tagName).toBe('A')
    const href = barra.getAttribute('href') ?? ''
    expect(href).toContain('/novo/epi/eventos?')
    const params = new URLSearchParams(href.split('?')[1])
    expect(params.get('start_date')).toBe(bucketIso)
    expect(new Date(params.get('end_date') ?? '').getTime() - inicioHora.getTime()).toBe(3_600_000)
  })

  it('linha de violações por classe leva pra lista filtrada pela classe', async () => {
    getSummary.mockResolvedValue({
      total: 12,
      by_class: [{ class: 'no_helmet', count: 12 }],
      by_camera: [],
    })
    montar()
    const painel = await screen.findByLabelText('Violações por classe')
    const linha = within(painel).getByRole('link', { name: /Sem capacete/ })
    const href = linha.getAttribute('href') ?? ''
    expect(href).toContain('/novo/epi/eventos?')
    expect(href).toContain('violation_type=no_helmet')
  })

  it('linha do ranking de câmeras leva pra lista filtrada por câmera, na janela de 30 dias', async () => {
    getSummary.mockResolvedValue({
      total: 5,
      by_class: [],
      by_camera: [{ camera_id: 'c1', camera_name: 'Entrada Expedição', count: 5 }],
    })
    montar()
    const painel = await screen.findByLabelText('Câmeras com mais eventos')
    const linha = within(painel).getByRole('link', { name: /Entrada Expedição/ })
    const href = linha.getAttribute('href') ?? ''
    expect(href).toContain('/novo/epi/eventos?')
    expect(href).toContain('camera_id=c1')
    // Ranking é sempre 30 dias — não é o recorte do turno selecionado.
    expect(href).toContain('start_date=')
  })

  it('câmera sem camera_id fica de pé mas sem link — filtro vazio mostraria tudo', async () => {
    getSummary.mockResolvedValue({
      total: 5,
      by_class: [],
      by_camera: [{ camera_id: null, camera_name: 'Sem nome', count: 5 }],
    })
    montar()
    const painel = await screen.findByLabelText('Câmeras com mais eventos')
    expect(within(painel).getByText('Sem nome')).toBeTruthy()
    expect(within(painel).queryByRole('link', { name: /Sem nome/ })).toBeNull()
  })

  it('KPI de eventos hoje leva pra lista da janela de hoje', async () => {
    montar()
    const cartao = await screen.findByLabelText('Eventos hoje')
    const link = within(cartao).getByRole('link', { name: /Eventos hoje: 23/ })
    const href = link.getAttribute('href') ?? ''
    expect(href).toContain('/novo/epi/eventos?')
    expect(href).toContain('start_date=')
    expect(href).toContain('end_date=')
  })

  it('vazio de eventos por hora oferece o caminho pros últimos 30 dias', async () => {
    montar()
    const painel = await screen.findByLabelText('Eventos por hora')
    expect(within(painel).getByText('Sem eventos no período.')).toBeTruthy()
    const cta = within(painel).getByRole('link', { name: /últimos 30 dias/ })
    expect((cta.getAttribute('href') ?? '')).toContain('/novo/epi/eventos?')
  })

  it('vazio de violações por classe oferece o caminho pros últimos 30 dias', async () => {
    montar()
    const painel = await screen.findByLabelText('Violações por classe')
    expect(within(painel).getByText('Sem violações no período.')).toBeTruthy()
    const cta = within(painel).getByRole('link', { name: /últimos 30 dias/ })
    expect((cta.getAttribute('href') ?? '')).toContain('/novo/epi/eventos?')
  })

  it('esconder um widget o tira da tela e a preferência sobrevive à remontagem', async () => {
    // `region` = o <section> do painel. O checkbox do popover carrega o mesmo
    // rótulo, e por nome só a busca pegaria os dois.
    const painel = () => screen.queryByRole('region', { name: 'Composição dos eventos' })

    const tela = montar()
    await screen.findByText('87')
    expect(painel()).toBeTruthy()

    fireEvent.click(screen.getByText('Personalizar widgets'))
    fireEvent.click(await screen.findByLabelText('Composição dos eventos', { selector: 'input' }))
    await waitFor(() => expect(painel()).toBeNull())

    tela.unmount()
    montar()
    await screen.findByText('87')
    expect(painel()).toBeNull()
  })

  it('os painéis novos entram no "Personalizar widgets", como os vizinhos', async () => {
    montar()
    await screen.findByText('87')
    fireEvent.click(screen.getByText('Personalizar widgets'))
    for (const rotulo of ['Violações por horário do dia', 'Volume por dia', 'Composição dos eventos']) {
      expect(await screen.findByLabelText(rotulo, { selector: 'input' })).toBeTruthy()
    }
  })
})

/**
 * O bloco que impede o painel de mentir. Cada widget novo tem DOIS casos: um
 * com dado (mostra o número que veio do banco) e um SEM dado (diz que não há,
 * em vez de desenhar barra de enfeite ou escrever zero como se fosse medição).
 */
describe('EPI Dashboard — perfil temporal (violações por horário, volume por dia, composição)', () => {
  it('lê o perfil pelo horário de CAPTURA, não pelo de ingestão', async () => {
    montar()
    await screen.findByText('87')
    // A linha do tempo de hoje também: sem `timeField: 'captured'` o painel
    // desenha a hora em que a carga rodou, não a hora da fábrica.
    await waitFor(() => expect(getTimeline).toHaveBeenCalled())
    const params = getTimeline.mock.calls.at(-1)?.[0] as { timeField?: string }
    expect(params.timeField).toBe('captured')
  })

  it('aponta a hora de PICO DE VIOLAÇÃO, não a hora de maior volume', async () => {
    getProfile.mockResolvedValue(PERFIL_RVB)
    montar()
    const painel = await screen.findByLabelText('Violações por horário do dia')
    // 13h UTC tem 40 violações em 137 eventos; 17h UTC tem 26 em 231. O pico
    // de VIOLAÇÃO é o das 13h — o de volume seria o das 17h.
    const horaLocal = String(new Date('2026-08-21T13:00:00Z').getHours()).padStart(2, '0')
    await waitFor(() =>
      expect(within(painel).getByText(`${horaLocal}h`, { selector: 'span' })).toBeTruthy(),
    )
    expect(within(painel).getByText('40')).toBeTruthy()
  })

  it('sem evento capturado, os três painéis dizem isso em vez de desenhar barra', async () => {
    montar()
    for (const nome of ['Violações por horário do dia', 'Volume por dia', 'Composição dos eventos']) {
      const painel = await screen.findByLabelText(nome)
      expect(within(painel).getByText('Nenhum evento capturado no período.')).toBeTruthy()
      // Nada de "0" ou "—" ocupando o lugar de um número que não existe.
      expect(within(painel).queryByText('—')).toBeNull()
      expect(within(painel).queryByRole('group')).toBeNull()
    }
  })

  it('a composição separa violação de conformidade — o total não é "tudo violação"', async () => {
    getProfile.mockResolvedValue(PERFIL_RVB)
    montar()
    const painel = await screen.findByLabelText('Composição dos eventos')
    await waitFor(() => expect(within(painel).getByText('66')).toBeTruthy())
    expect(within(painel).getByText('302')).toBeTruthy()
    expect(within(painel).getByText('55')).toBeTruthy()
    expect(within(painel).getByText('Conformidade (EPI em uso)')).toBeTruthy()
    expect(within(painel).getByText('Não definida')).toBeTruthy()
    // 66 de 423 = 16%, e a frase tem de dizer isso e não "423 violações".
    expect(within(painel).getByText(/16% dos 423 eventos do período são violação/)).toBeTruthy()
  })

  it('mostra a revisão humana e a confiança média que vieram da API', async () => {
    getProfile.mockResolvedValue(PERFIL_RVB)
    montar()
    const painel = await screen.findByLabelText('Composição dos eventos')
    await waitFor(() => expect(within(painel).getByText(/122/)).toBeTruthy())
    expect(within(painel).getByText(/60 procedentes · 62 descartados/)).toBeTruthy()
    expect(within(painel).getByText('56%')).toBeTruthy()
    expect(within(painel).getByText('14')).toBeTruthy()
  })

  it('declara o alcance REAL do dado em vez de deixar supor 90 dias de operação', async () => {
    getProfile.mockResolvedValue(PERFIL_RVB)
    montar()
    const painel = await screen.findByLabelText('Violações por horário do dia')
    // 2 dias com registro (21 e 23/08) numa série de 3 dias — o buraco de 22
    // aparece no gráfico e não conta como dia operado.
    await waitFor(() =>
      expect(within(painel).getByText(/21\/08 a 23\/08 · 2 dia\(s\) com registro/)).toBeTruthy(),
    )
  })

  it('"Aguardando tratativa" traz o número real de eventos sem reconhecimento', async () => {
    getProfile.mockResolvedValue(PERFIL_RVB)
    montar()
    const cartao = await screen.findByLabelText('Aguardando tratativa')
    expect(within(cartao).getByText('396')).toBeTruthy()
    expect(within(cartao).getByText('Sem reconhecimento')).toBeTruthy()
    expect(within(cartao).getByText(/de 423 evento\(s\) no período/)).toBeTruthy()
  })

  it('sem perfil carregado o cartão de tratativa não entra — não inventa um zero', async () => {
    getProfile.mockRejectedValue(new Error('timeout'))
    montar()
    await screen.findByText('87')
    await waitFor(() => expect(screen.queryByLabelText('Aguardando tratativa')).toBeNull())
  })
})
