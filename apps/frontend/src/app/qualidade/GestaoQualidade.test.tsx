/**
 * Gestão é PROVA. O que estes testes seguram, em ordem de importância:
 *
 *  1. nenhum número na tela que uma rota não tenha devolvido — e, em especial,
 *     nenhum dos números do desenho que o backend NÃO serve ("% dúvida",
 *     "latência p95", "idade máx 38 min", "4/4 pontos", tendência de 30 dias);
 *  2. nenhum controle que não chegue a lugar nenhum: os dois botões de export
 *     do desenho ficam no lugar, DESABILITADOS e com `title` dizendo por quê;
 *  3. o recorte que a tela mostra é o recorte que o backend aplica — o seletor
 *     de período só existe onde a rota aceita período, e a lista de peças avisa
 *     que data/tipo são descartados;
 *  4. UUID não vai para a tela: operador vira nome, câmera vira nome;
 *  5. os quatro estados existem: carregado / carregando / vazio / erro com a
 *     rota e retry.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  permissoes: new Set<string>(),
  temModulo: true,
}))

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => mocks.permissoes.has(p), hasModule: () => mocks.temModulo }),
}))

vi.mock('../../services/api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../../services/api')>()
  return { ...real, api: { ...real.api, get: mocks.get } }
})

import { ApiError } from '../../services/api'
import { GestaoQualidade } from './GestaoQualidade'

// ── Respostas reais das rotas (formas medidas no backend) ───────────────────

const RESUMO = {
  data: {
    summary: {
      pieces_total: 148,
      ok_pct: 87.2,
      nok_count: 9,
      rework_active: 3,
      stations_active: 2,
      stations_total: 4,
    },
    updated_at: '2026-08-29T12:00:00+00:00',
  },
}

const ESTACOES = {
  data: {
    stations: [
      {
        id: '5e0c0f1a-0000-4000-8000-000000000001',
        station_code: 'EST.1',
        name: 'Bancada A — corte',
        camera_ids: [],
        online: true,
        operator: { id: 'e1d2c3b4-0000-4000-8000-000000000009', name: 'Sandra Alves' },
        active_piece: {
          op: 'OP 2024-1187',
          code: 'AN-24-0785',
          product_type: 'Anel plano',
          status: 'rework_v1',
          status_label: 'Retrabalho V1',
          started_at: '2026-08-29T11:40:00+00:00',
        },
        shift_stats: { ok: 0, nok: 0 },
        status: 'warning',
      },
    ],
    updated_at: '2026-08-29T12:00:00+00:00',
  },
}

const RETRABALHO = {
  data: {
    stats: {
      by_validation: { v1: 19, v2: 8 },
      avg_rework_duration_seconds: 160,
      most_common_defect: 'madeira exposta',
    },
  },
}

const CATEGORIAS = {
  data: {
    categories: [
      { slug: 'visual', label: 'Visual (risco/arranhão/mancha)' },
      { slug: 'dimensional', label: 'Dimensional (fora de tolerância)' },
    ],
  },
}

/** `/inspections/summary` devolve as métricas DIRETO em `data` (sem "summary"). */
const INSPECOES = {
  data: {
    total: 152,
    ok: 141,
    nok: 11,
    ok_rate: 92.76,
    nok_rate: 7.24,
    pending_feedback: 7,
    confirmed: 120,
    rejected: 4,
    retrain_requested: 2,
    cep_alerts_count: 0,
    defect_distribution: { visual: 14, dimensional: 5 },
    shift: 'morning',
  },
}

const PECA_A = {
  id: 'aaaaaaa1-0000-4000-8000-000000000001',
  piece_number: 'AN-24-0785',
  work_order: 'OP 2024-1187',
  product_type: 'Anel plano',
  status: 'approved',
  current_station: 'bench_b',
  started_at: '2026-08-29T09:00:00+00:00',
  completed_at: '2026-08-29T09:06:12+00:00',
  total_rework_count: 0,
  total_rework_time_seconds: 0,
  wiser_exported: true,
  wiser_exported_at: '2026-08-29T09:07:00+00:00',
}

const PECA_B = {
  ...PECA_A,
  id: 'aaaaaaa1-0000-4000-8000-000000000002',
  piece_number: 'AN-24-0781',
  status: 'rework_v2',
  completed_at: null,
  total_rework_count: 2,
  wiser_exported: false,
  wiser_exported_at: null,
}

const PECAS = { data: { pieces: [PECA_A, PECA_B], total: 2, page: 1, per_page: 20 } }

const REWORKS = {
  data: {
    reworks: [
      {
        id: 'bbbbbbb1-0000-4000-8000-000000000001',
        piece_id: PECA_A.id,
        validation_type: 'v1',
        defect_type: 'distancia',
        defect_description: 'Distância 13,4 mm',
        photo_before_r2_key: 'quality/antes.jpg',
        photo_after_r2_key: 'quality/depois.jpg',
        started_at: '2026-08-29T09:18:00+00:00',
        completed_at: '2026-08-29T09:20:40+00:00',
        duration_seconds: 160,
        attempt_number: 1,
        notes: null,
      },
    ],
    total: 1,
  },
}

const TURNO = {
  data: {
    shift: 'morning',
    date: '2026-08-29',
    total: 152,
    total_ok: 141,
    total_nok: 11,
    nok_rate: 0.0724,
    defect_pareto: [
      { defect_class: 'madeira_exposta', count: 8, pct: 0.7273 },
      { defect_class: 'transpasse', count: 3, pct: 0.2727 },
    ],
    generated_at: '2026-08-29T12:00:00+00:00',
  },
}

const CAMERAS = {
  data: {
    cameras: [{ id: 'cccccccc-0000-4000-8000-000000000001', name: 'Bancada A · topo' }],
  },
}

/** Roteia por caminho — sem isso `/cameras` receberia a resposta do relatório. */
function responde(sobrescreve: Record<string, unknown> = {}) {
  const tabela: Array<[string, unknown]> = [
    ['/v1/quality/dashboard/summary', RESUMO],
    ['/v1/quality/dashboard/stations', ESTACOES],
    ['/v1/quality/gate/stats/rework', RETRABALHO],
    ['/v1/quality/defect-categories', CATEGORIAS],
    ['/v1/quality/inspections/summary', INSPECOES],
    ['/v1/quality/gate/pieces', PECAS],
    ['/v1/quality/gate/reworks', REWORKS],
    ['/v1/quality/reports/shift', TURNO],
    ['/v1/quality/cameras', CAMERAS],
  ]
  mocks.get.mockImplementation((rota: string) => {
    for (const [chave, valor] of Object.entries(sobrescreve)) {
      if (rota.startsWith(chave)) {
        return valor instanceof Error ? Promise.reject(valor) : Promise.resolve(valor)
      }
    }
    // `/gate/reworks` antes de `/gate/pieces` não colide (prefixos distintos),
    // mas a ordem importa para `/inspections/summary` vs `/inspections`.
    for (const [chave, valor] of tabela) {
      if (rota.startsWith(chave)) return Promise.resolve(valor)
    }
    return Promise.reject(new ApiError(`rota não mockada: ${rota}`, 404))
  })
}

const chamadas = (prefixo: string) =>
  mocks.get.mock.calls.map((c) => String(c[0])).filter((r) => r.startsWith(prefixo))

const abrirAba = (nome: string) => fireEvent.click(screen.getByRole('tab', { name: nome }))

beforeEach(() => {
  mocks.get.mockReset()
  mocks.permissoes = new Set(['reports:read', 'reports:export'])
  mocks.temModulo = true
})

// ── módulo desligado (nota do cético do flip) ───────────────────────────────

it('sem o módulo quality, a tela bloqueia e não chama rota nenhuma', () => {
  mocks.temModulo = false
  render(<GestaoQualidade />)
  expect(screen.getByText('Módulo não habilitado')).toBeTruthy()
  expect(mocks.get).not.toHaveBeenCalled()
})

// ── D1 · Dashboard ──────────────────────────────────────────────────────────

describe('D1 — o painel mostra o que a rota devolveu, e só', () => {
  it('os KPIs saem de dashboard/summary e de inspections/summary', async () => {
    responde()
    render(<GestaoQualidade />)

    expect(await screen.findByText('148')).toBeTruthy() // pieces_total
    expect(screen.getByText('87,2')).toBeTruthy() // ok_pct
    expect(screen.getByText('9')).toBeTruthy() // nok_count
    expect(screen.getByText('3')).toBeTruthy() // rework_active
    expect(screen.getByText('2/4')).toBeTruthy() // stations_active/total
    await waitFor(() => expect(screen.getAllByText('7').length).toBeGreaterThan(0)) // pending_feedback
  })

  it('não inventa os KPIs que o backend não tem', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')

    // "% DÚVIDA" não existe: quality_inspections.result só tem ok/nok.
    expect(screen.queryByText(/%\s*dúvida/i)).toBeNull()
    // "LATÊNCIA P95": não há coluna de latência em tabela nenhuma.
    expect(screen.queryByText(/latência/i)).toBeNull()
    // "idade máx 38 min": não há agregação de MIN(created_at) dos pendentes.
    expect(screen.queryByText(/idade máx/i)).toBeNull()
    // Tendência de 30 dias exigiria 30 chamadas — a rota agrega o período todo.
    expect(screen.queryByText(/tendência/i)).toBeNull()
  })

  it('rotula o eixo pelo dado real (validação v1/v2/v3), não como "ponto"', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')

    expect(screen.getByRole('img', { name: 'V1: 19' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'V2: 8' })).toBeTruthy()
    // Nada de P1/P2/P4/P8: nenhuma rota agrega por ponto.
    expect(screen.queryByRole('img', { name: /^P\d/ })).toBeNull()
  })

  it('nomeia a categoria de defeito pela rota /defect-categories', async () => {
    responde()
    render(<GestaoQualidade />)

    // slug cru ("visual") nunca chega à tela quando o rótulo existe
    expect(await screen.findByRole('img', { name: 'Visual (risco/arranhão/mancha): 14' })).toBeTruthy()
  })

  it('o período vai como date_from/date_to para a única rota que o aceita', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')

    fireEvent.change(screen.getByLabelText('Período das inspeções'), { target: { value: 'trinta' } })

    await waitFor(() => expect(chamadas('/v1/quality/inspections/summary').length).toBe(2))
    const ultima = chamadas('/v1/quality/inspections/summary').at(-1) as string
    expect(ultima).toContain('date_from=')
    expect(ultima).toContain('date_to=')

    // E NÃO vai para as rotas que ignoram período — nenhuma delas foi refeita
    // com parâmetro de data.
    expect(chamadas('/v1/quality/dashboard/summary').every((r) => !r.includes('date_'))).toBe(true)
    expect(chamadas('/v1/quality/gate/stats/rework').every((r) => !r.includes('date_'))).toBe(true)
  })

  it('mostra o NOME do operador da estação, nunca o UUID', async () => {
    responde()
    render(<GestaoQualidade />)

    expect(await screen.findByText(/Sandra Alves/)).toBeTruthy()
    expect(screen.queryByText(/e1d2c3b4/)).toBeNull()
  })

  it('não exibe online nem shift_stats — são valores fixos no código do backend', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')

    // nem selo "Online" (sempre true no backend) nem placar 0/0 do turno
    expect(screen.queryByText('Online')).toBeNull()
    expect(screen.queryByText(/\b0\s*ok\b/i)).toBeNull()
    // e a tela DIZ por que esses dois campos ficaram de fora
    expect(screen.getByText(/valores fixos no código do/)).toBeTruthy()
  })

  it('erro na rota principal: mostra a rota, o status e um retry', async () => {
    responde({ '/v1/quality/dashboard/summary': new ApiError('boom', 503) })
    render(<GestaoQualidade />)

    expect(await screen.findByText(/dashboard\/summary · 503/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    await waitFor(() => expect(chamadas('/v1/quality/dashboard/summary').length).toBe(2))
  })

  it('falha de um cartão não derruba o painel', async () => {
    responde({ '/v1/quality/gate/stats/rework': new ApiError('boom', 500) })
    render(<GestaoQualidade />)

    expect(await screen.findByText('148')).toBeTruthy() // KPIs seguem de pé
    expect(screen.getByText(/gate\/stats\/rework · 500/)).toBeTruthy()
  })

  it('vazio honesto quando não há retrabalho nem categoria', async () => {
    responde({
      '/v1/quality/gate/stats/rework': {
        data: { stats: { by_validation: {}, avg_rework_duration_seconds: 0, most_common_defect: null } },
      },
      '/v1/quality/inspections/summary': {
        data: { ...INSPECOES.data, defect_distribution: {} },
      },
    })
    render(<GestaoQualidade />)

    expect(await screen.findByText('Nenhum retrabalho registrado.')).toBeTruthy()
    expect(screen.getByText(/Nenhuma inspeção com categoria de defeito/)).toBeTruthy()
  })

  it('carregando: o loader da casa, não uma tela em branco', () => {
    mocks.get.mockImplementation(() => new Promise(() => {}))
    const { container } = render(<GestaoQualidade />)
    expect(container.querySelector('[aria-busy="true"]')).toBeTruthy()
  })
})

// ── D2 · Peças & OPs ────────────────────────────────────────────────────────

describe('D2 — a lista de peças diz o que o backend realmente filtra', () => {
  it('traduz o status cru da máquina de estados, mantendo o enum no title', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')

    const lista = await screen.findByRole('group', { name: 'Peças' })
    expect(within(lista).getByText('AN-24-0785')).toBeTruthy()
    // "Aprovada"/"Retrabalho V2" também existem como <option> do filtro — o que
    // importa é que a LINHA da peça mostre o rótulo, não o enum.
    expect(within(lista).getByText('Aprovada')).toBeTruthy()
    expect(within(lista).getByText('Retrabalho V2')).toBeTruthy()
    // o enum continua acessível, mas não é o que a pessoa lê
    expect(screen.getByTitle('status: approved')).toBeTruthy()
    expect(screen.queryByText('approved')).toBeNull()
  })

  it('o tempo de ciclo é a subtração dos dois timestamps que a rota devolveu', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')

    // 09:00:00 → 09:06:12
    expect(await screen.findByText('6:12')).toBeTruthy()
    // peça sem completed_at não ganha cronômetro inventado
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('não mostra a coluna "pontos" do desenho — não existe contador de etapas', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')
    await screen.findByRole('group', { name: 'Peças' })

    expect(screen.queryByText('4/4 ✓')).toBeNull()
    expect(screen.queryByText(/^\d\/4$/)).toBeNull()
  })

  it('avisa que data e tipo de produto são descartados pela rota', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')

    expect(
      await screen.findByText(/só filtra por status e OP\. Data e tipo de produto são ignorados/),
    ).toBeTruthy()
    // e não existe seletor de período nesta aba
    expect(screen.queryByLabelText('Período das inspeções')).toBeNull()
  })

  it('status e OP vão para a query da rota', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')
    await screen.findByRole('group', { name: 'Peças' })

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'rework_v2' } })
    await waitFor(() =>
      expect(chamadas('/v1/quality/gate/pieces').at(-1)).toContain('status=rework_v2'),
    )

    fireEvent.change(screen.getByLabelText('Ordem de produção'), { target: { value: 'OP 2024-1187' } })
    fireEvent.click(screen.getByRole('button', { name: 'Filtrar' }))
    await waitFor(() =>
      expect(chamadas('/v1/quality/gate/pieces').at(-1)).toContain('work_order=OP+2024-1187'),
    )
  })

  it('a paginação não mente: sem contagem total, só "página N"', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')

    expect(await screen.findByText('Página 1')).toBeTruthy()
    expect(screen.queryByText(/de \d+ páginas?/)).toBeNull()
    // página com 2 itens (< per_page) → não há próxima que se possa prometer
    expect(screen.getByRole('button', { name: 'Próxima →' }).hasAttribute('disabled')).toBe(true)
  })

  it('o detalhe traz os retrabalhos da peça e a foto que não há como servir', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')
    await screen.findByRole('group', { name: 'Peças' })

    await waitFor(() =>
      expect(chamadas('/v1/quality/gate/reworks').at(-1)).toContain(`piece_id=${PECA_A.id}`),
    )

    const painel = await screen.findByRole('complementary', { name: 'Detalhe da peça' })
    expect(within(painel).getByText('V1')).toBeTruthy()
    expect(within(painel).getByText(/distancia/)).toBeTruthy()
    expect(within(painel).getByText(/2:40/)).toBeTruthy() // duration_seconds = 160

    // a caixa de foto do desenho fica — vazia, e dizendo por quê
    const foto = within(painel).getByText('sem foto')
    expect(foto.getAttribute('title')).toMatch(/Sem rota que assine a URL/)
    expect(painel.querySelector('img')).toBeNull()
  })

  it('trocar de peça troca o piece_id da consulta de retrabalhos', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')

    fireEvent.click(await screen.findByText('AN-24-0781'))
    await waitFor(() =>
      expect(chamadas('/v1/quality/gate/reworks').at(-1)).toContain(`piece_id=${PECA_B.id}`),
    )
  })

  it('vazio honesto e erro com rota + retry', async () => {
    responde({ '/v1/quality/gate/pieces': { data: { pieces: [], total: 0, page: 1, per_page: 20 } } })
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Peças & OPs')
    expect(await screen.findByText('Nenhuma peça neste recorte')).toBeTruthy()

    responde({ '/v1/quality/gate/pieces': new ApiError('boom', 500) })
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'approved' } })
    expect(await screen.findByText(/gate\/pieces · 500/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    await waitFor(() => expect(chamadas('/v1/quality/gate/pieces').length).toBeGreaterThan(2))
  })
})

// ── D3 · Relatórios ─────────────────────────────────────────────────────────

describe('D3 — o relatório do turno, e os dois botões que não têm rota', () => {
  it('Exportar WISER e CSV ficam no lugar, desabilitados, dizendo por quê', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Relatórios')

    const wiser = await screen.findByRole('button', { name: 'Exportar WISER' })
    expect(wiser.hasAttribute('disabled')).toBe(true)
    expect(wiser.getAttribute('title')).toMatch(/Sem rota/)

    const csv = screen.getByRole('button', { name: 'CSV' })
    expect(csv.hasAttribute('disabled')).toBe(true)
    expect(csv.getAttribute('title')).toMatch(/Sem rota/)
  })

  it('os números vêm de /reports/shift — nok_rate é fração e vira percentual', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Relatórios')

    expect(await screen.findByText('152')).toBeTruthy() // total
    expect(screen.getByText('141')).toBeTruthy() // total_ok
    expect(screen.getByText('11')).toBeTruthy() // total_nok
    expect(screen.getByText('7,2')).toBeTruthy() // 0.0724 → 7,24 → 7,2
  })

  it('a tabela é o pareto por classe — não as colunas por ponto do desenho', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Relatórios')

    const tabela = await screen.findByRole('group', { name: 'Pareto de defeitos do turno' })
    expect(within(tabela).getByText('madeira_exposta')).toBeTruthy()
    expect(within(tabela).getByText('72,7%')).toBeTruthy()
    // as colunas do desenho que nenhuma rota agrega não entram na tabela
    expect(within(tabela).queryByText(/fotos/i)).toBeNull()
    expect(within(tabela).queryByText(/ponto/i)).toBeNull()
    expect(within(tabela).queryByText(/retrabalho/i)).toBeNull()
  })

  it('turno, data e câmera entram na query; a câmera aparece por NOME', async () => {
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Relatórios')
    await screen.findByText('152')

    fireEvent.change(screen.getByLabelText('Turno'), { target: { value: 'night' } })
    await waitFor(() => expect(chamadas('/v1/quality/reports/shift').at(-1)).toContain('shift=night'))

    fireEvent.change(screen.getByLabelText('Câmera'), { target: { value: CAMERAS.data.cameras[0].id } })
    await waitFor(() =>
      expect(chamadas('/v1/quality/reports/shift').at(-1)).toContain(
        `camera_id=${CAMERAS.data.cameras[0].id}`,
      ),
    )
    expect(screen.getByRole('option', { name: 'Bancada A · topo' })).toBeTruthy()
  })

  it('sem reports:export a tela diz que a permissão faltará quando a rota existir', async () => {
    mocks.permissoes = new Set(['reports:read'])
    responde()
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Relatórios')

    expect(await screen.findByText(/não tem/)).toBeTruthy()
    expect(screen.getByText('reports:export')).toBeTruthy()
  })

  it('vazio honesto: turno sem defeito classificado', async () => {
    responde({
      '/v1/quality/reports/shift': { data: { ...TURNO.data, defect_pareto: [] } },
    })
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Relatórios')

    expect(await screen.findByText('Sem defeitos classificados neste turno')).toBeTruthy()
  })

  it('erro: rota, status e retry', async () => {
    responde({ '/v1/quality/reports/shift': new ApiError('boom', 500) })
    render(<GestaoQualidade />)
    await screen.findByText('148')
    abrirAba('Relatórios')

    expect(await screen.findByText(/reports\/shift · 500/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    await waitFor(() => expect(chamadas('/v1/quality/reports/shift').length).toBe(2))
  })
})
