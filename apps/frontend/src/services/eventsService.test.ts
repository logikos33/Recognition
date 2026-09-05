/**
 * O funil PADRÃO do usuário mostra evento REAL (issue #677).
 *
 * `GET /api/v1/events/timeline` e `/search` fazem
 * `include_demo = request.args.get("include_demo","true") != "false"`: quem
 * não manda o parâmetro recebe `public.demo_events` unido por `UNION ALL` ao
 * evento de verdade. Este cliente nunca mandava — o painel "Eventos por hora"
 * somaria evento semeado ao real sem dizer, contra a decisão registrada (o
 * semeado só aparece por filtro DECLARADO na tela).
 *
 * Hoje `count(*) FROM public.demo_events` = 0 no DEV: o defeito é INERTE e
 * passa a mentir no minuto em que alguém semear a primeira demonstração. É
 * por isso que ele tem teste e não espera o incidente.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn((_rota: string) => Promise.resolve({ success: true, data: undefined }))

vi.mock('./api', () => ({ api: { get: (rota: string) => get(rota) } }))

const { eventsService } = await import('./eventsService')

const JANELA = { from: '2026-08-25T00:00:00Z', to: '2026-08-25T23:59:59Z' }

/** Querystring da última chamada — o que de fato viajou até a rota. */
function ultimaQuery(): URLSearchParams {
  const rota = get.mock.calls.at(-1)?.[0] ?? ''
  return new URLSearchParams(rota.split('?')[1] ?? '')
}

beforeEach(() => get.mockClear())

describe('eventsService — política de dado de demonstração', () => {
  it('getTimeline pede include_demo=false: o default da ROTA é incluir', async () => {
    await eventsService.getTimeline({ ...JANELA, bucket: 'hour', moduleCode: 'epi' })
    // Ausente ≠ false: a rota trata ausência como `true`. Tem de ir escrito.
    expect(ultimaQuery().get('include_demo')).toBe('false')
  })

  it('getSummary e getProfile seguem a mesma política', async () => {
    await eventsService.getSummary({ ...JANELA, moduleCode: 'epi' })
    expect(ultimaQuery().get('include_demo')).toBe('false')
    await eventsService.getProfile({ ...JANELA, moduleCode: 'epi' })
    expect(ultimaQuery().get('include_demo')).toBe('false')
  })

  it('quem QUER demonstração pede explicitamente — e aí ela entra', async () => {
    await eventsService.getTimeline({ ...JANELA, includeDemo: true })
    expect(ultimaQuery().get('include_demo')).toBe('true')
  })

  it('o eixo de tempo continua declarado junto (time_field=captured)', async () => {
    await eventsService.getTimeline({ ...JANELA, timeField: 'captured' })
    const q = ultimaQuery()
    expect(q.get('time_field')).toBe('captured')
    expect(q.get('include_demo')).toBe('false')
  })
})

/**
 * Achado do cético: o eixo estava declarado SÓ no `getTimeline`. O resumo
 * alimenta "Violações por classe" e "Câmeras com mais eventos" — dois painéis
 * da MESMA tela, com deep-link para `GET /api/alerts`, que recorta pela
 * CAPTURA desde a issue #676. Sem o parâmetro, a rota conta pela GRAVAÇÃO e o
 * cartão volta a discordar da lista que ele abre.
 */
describe('eventsService — eixo do tempo em TODO pedido', () => {
  it('getSummary declara CAPTURA sem ninguém pedir', async () => {
    await eventsService.getSummary({ ...JANELA, moduleCode: 'epi' })
    expect(ultimaQuery().get('time_field')).toBe('captured')
  })

  it('getProfile e getTimeline idem — um eixo só para a tela inteira', async () => {
    await eventsService.getProfile({ ...JANELA, moduleCode: 'epi' })
    expect(ultimaQuery().get('time_field')).toBe('captured')
    await eventsService.getTimeline({ ...JANELA, bucket: 'hour' })
    expect(ultimaQuery().get('time_field')).toBe('captured')
  })

  it('quem quer o eixo da INGESTÃO pede — e o parâmetro sai uma vez só', async () => {
    await eventsService.getTimeline({ ...JANELA, bucket: 'hour', timeField: 'created' })
    const rota = get.mock.calls.at(-1)?.[0] ?? ''
    expect(ultimaQuery().get('time_field')).toBe('created')
    expect(rota.match(/time_field=/g)).toHaveLength(1)
  })
})
