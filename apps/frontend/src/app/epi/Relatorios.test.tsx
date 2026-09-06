/**
 * Relatório é PROVA. O que estes testes seguram, em ordem de importância:
 *
 *  1. nenhum número na tela que a API não tenha devolvido — e nenhum controle
 *     que não chegue a lugar nenhum (digest, checkbox de conteúdo);
 *  2. `reports:export` é permissão PRÓPRIA, separada de `reports:read`: quem lê
 *     o relatório não necessariamente pode exportá-lo;
 *  3. o export bate no endpoint certo, com o período que está na tela;
 *  4. os quatro estados do desenho existem: carregado / loading / vazio / erro.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  downloadBlob: vi.fn(),
  permissoes: new Set<string>(),
}))

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => mocks.permissoes.has(p) }),
}))

vi.mock('../../services/api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../../services/api')>()
  return {
    ...real,
    api: { ...real.api, get: mocks.get, downloadBlob: mocks.downloadBlob },
  }
})

import { ApiError } from '../../services/api'
import { Relatorios } from './Relatorios'

const HORA_PICO = '2026-08-03T14:00:00+00:00'

const RESPOSTA = {
  data: {
    summary: {
      compliance_rate: 82.4,
      total_violations: 31,
      top_cameras: [{ camera_id: 'cam-04-expedicao', count: 14 }],
      trend_by_hour: [
        { hour: '2026-08-03T09:00:00+00:00', count: 3 },
        { hour: HORA_PICO, count: 12 },
      ],
    },
    pdf_url: 'https://r2.exemplo/compliance.pdf?sig=abc',
    period: { period: 'semana', from: '2026-07-28T00:00:00+00:00', to: '2026-08-03T12:00:00+00:00' },
  },
}

/**
 * A tela também busca `/cameras` para dar NOME ao "Top câmera" — o agregado
 * devolve só `camera_id`, e UUID na tela não é dado real, é dado ilegível.
 * Sem rotear o mock por rota, `/cameras` receberia a resposta do relatório.
 */
const CAMERAS = { data: { cameras: [{ id: 'cam-04-expedicao', name: 'Entrada Expedição 04' }] } }

/** Responde o relatório em `/reports/*` e a lista de câmeras em `/cameras`. */
const responde = (relatorio: unknown) =>
  mocks.get.mockImplementation((rota: string) =>
    rota.startsWith('/cameras') ? Promise.resolve(CAMERAS) : Promise.resolve(relatorio),
  )

/** Chamadas ao relatório, ignorando as de `/cameras`. */
const chamadasDeRelatorio = () =>
  mocks.get.mock.calls.filter((c) => !String(c[0]).startsWith('/cameras'))

const VAZIO = {
  data: {
    // Vazio de verdade: o backend agora anula o score em vez de mandar 100.
    summary: {
      compliance_rate: null,
      compliance_reason: 'sem_sinal_no_periodo',
      total_violations: 0,
      top_cameras: [],
      trend_by_hour: [],
    },
    pdf_url: 'https://r2.exemplo/vazio.pdf',
    period: { period: 'semana', from: '', to: '' },
  },
}

beforeEach(() => {
  mocks.get.mockReset()
  mocks.downloadBlob.mockReset()
  mocks.permissoes = new Set(['reports:read', 'reports:export'])
  // jsdom não implementa object URL nem navegação de <a download>.
  Object.defineProperty(URL, 'createObjectURL', { writable: true, value: vi.fn(() => 'blob:x') })
  Object.defineProperty(URL, 'revokeObjectURL', { writable: true, value: vi.fn() })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
})

const carregado = () => screen.findByRole('heading', { name: 'Relatórios' })

describe('o que a tela mostra é o que a API devolveu', () => {
  it('score, total e top câmera saem do /reports/compliance — nada calculado aqui', async () => {
    responde(RESPOSTA)
    render(<Relatorios />)
    await carregado()

    expect(screen.getByText('82')).toBeTruthy()            // round(82.4)
    expect(screen.getByText('31')).toBeTruthy()            // total_violations
    // NOME, nunca o identificador: o operador não sabe qual das 29 câmeras é
    // `eb1501db-…`. O id só apareceria se a tela desistisse de resolvê-lo.
    expect(screen.getByText('Entrada Expedição 04')).toBeTruthy()
    expect(screen.queryByText('cam-04-expedicao')).toBeNull()
    expect(screen.getByText('14')).toBeTruthy()

    // pico derivado do trend_by_hour da resposta, no fuso de quem lê
    const esperado = `${String(new Date(HORA_PICO).getHours()).padStart(2, '0')}h`
    expect(screen.getByText(esperado)).toBeTruthy()
  })

  it('chama o endpoint real com from/to e o period obrigatório', async () => {
    responde(RESPOSTA)
    render(<Relatorios />)
    await carregado()

    const url = chamadasDeRelatorio()[0][0] as string
    expect(url.startsWith('/reports/compliance?')).toBe(true)
    const q = new URLSearchParams(url.split('?')[1])
    expect(q.get('period')).toBe('semana')
    expect(q.get('from')).toBeTruthy()
    expect(q.get('to')).toBeTruthy()
  })

  it('NÃO renderiza o digest nem as checkboxes de conteúdo — a API não os serve', async () => {
    responde(RESPOSTA)
    const { container } = render(<Relatorios />)
    await carregado()

    expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
    expect(screen.queryAllByRole('switch')).toHaveLength(0)
    expect(screen.queryByLabelText(/destinat/i)).toBeNull()
    expect(screen.queryByLabelText(/horário de envio/i)).toBeNull()
    // destinatários e ações de exemplo do protótipo não podem vazar para a tela
    expect(container.textContent).not.toContain('@rvb.com.br')
    expect(container.textContent).not.toContain('Juliana')
  })

  it('não explica ao operador o que falta na API', async () => {
    // A tela chegou a trazer um parágrafo dizendo quais dados o backend não
    // serve. Isso é nota de desenvolvedor: quem opera não tem o que fazer com
    // ela, e ela ocupa a tela toda vez. A lacuna vive na lista do design, não
    // no produto. O que a tela deve fazer é simplesmente NÃO exibir o que não
    // tem — e é o teste acima que segura isso.
    responde(RESPOSTA)
    const { container } = render(<Relatorios />)
    await carregado()
    expect(container.textContent).not.toMatch(/lacuna|não existe na API|heur[íi]stica do backend/i)
  })
})

describe('reports:export é permissão própria', () => {
  it('quem só tem reports:read não consegue exportar, e a tela diz por quê', async () => {
    mocks.permissoes = new Set(['reports:read'])
    responde(RESPOSTA)
    render(<Relatorios />)
    await carregado()

    const botao = screen.getByRole('button', { name: /exportar/i }) as HTMLButtonElement
    expect(botao.disabled).toBe(true)
    expect(screen.getByText(/sem permissão para exportar/i)).toBeTruthy()
  })

  it('com reports:export o botão funciona', async () => {
    responde(RESPOSTA)
    render(<Relatorios />)
    await carregado()
    expect((screen.getByRole('button', { name: /exportar/i }) as HTMLButtonElement).disabled)
      .toBe(false)
  })
})

describe('export', () => {
  it('CSV baixa de /alerts/export com o intervalo da tela', async () => {
    responde(RESPOSTA)
    mocks.downloadBlob.mockResolvedValue(new Blob(['a,b']))
    render(<Relatorios />)
    await carregado()

    fireEvent.click(screen.getByRole('button', { name: /^exportar$/i }))
    await waitFor(() => expect(mocks.downloadBlob).toHaveBeenCalled())

    const url = mocks.downloadBlob.mock.calls[0][0] as string
    expect(url.startsWith('/alerts/export?')).toBe(true)
    const q = new URLSearchParams(url.split('?')[1])
    expect(q.get('start_date')).toBeTruthy()
    expect(q.get('end_date')).toBeTruthy()
    expect(await screen.findByText(/arquivo do período/i)).toBeTruthy()
  })

  it('PDF refaz a chamada (link presignado vence em 1h) e usa o pdf_url da resposta', async () => {
    responde(RESPOSTA)
    render(<Relatorios />)
    await carregado()

    fireEvent.click(screen.getByRole('button', { name: 'PDF' }))
    fireEvent.click(screen.getByRole('button', { name: /^exportar$/i }))

    await waitFor(() => expect(chamadasDeRelatorio()).toHaveLength(2))
    expect(mocks.downloadBlob).not.toHaveBeenCalled()
    expect(await screen.findByText(/arquivo do período/i)).toBeTruthy()
  })

  it('falha do export mostra o motivo e o código — sem a rota (issue #810)', async () => {
    responde(RESPOSTA)
    mocks.downloadBlob.mockRejectedValue(new Error('HTTP 502'))
    render(<Relatorios />)
    await carregado()

    fireEvent.click(screen.getByRole('button', { name: /^exportar$/i }))
    expect(
      await screen.findByText(/não foi possível gerar o arquivo.*código 502/i),
    ).toBeTruthy()
    expect(screen.queryByText(/\/alerts\/export/)).toBeNull()
  })
})

describe('estados da rota', () => {
  it('loading mostra o LogikosLoader', () => {
    mocks.get.mockReturnValue(new Promise(() => {}))
    render(<Relatorios />)
    expect(screen.getByText('CARREGANDO RELATÓRIOS')).toBeTruthy()
  })

  it('vazio é honesto e oferece ampliar o intervalo', async () => {
    responde(VAZIO)
    render(<Relatorios />)
    expect(await screen.findByText(/sem dados no período selecionado/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Últimos 30 dias' })).toBeTruthy()
  })

  /**
   * IRMÃ do score do Dashboard. O mesmo número de conformidade chega aqui por
   * `GET /api/reports/compliance`, e este caminho tinha o defeito na forma mais
   * cara: `except Exception: compliance_rate = 100.0` no `_aggregate`. Banco
   * fora do ar = relatório perfeito, impresso num PDF que sobe para o R2.
   */
  it('score não apurado é travessão, nunca 0 e nunca 100', async () => {
    responde({
      data: {
        ...RESPOSTA.data,
        summary: {
          ...RESPOSTA.data.summary,
          compliance_rate: null,
          compliance_reason: 'nao_foi_possivel_apurar',
        },
      },
    })
    render(<Relatorios />)
    await carregado()
    expect(screen.getByText('—')).toBeTruthy()
    expect(screen.getByText(/score não apurado/i)).toBeTruthy()
    // `Math.round(null)` é 0 — e 0 nesta tela lê-se "conformidade zero".
    expect(screen.queryByText('0')).toBeNull()
  })

  /**
   * #789 NA TELA IRMÃ. O cético desta rodada mediu: o PR que reservou o 100 ao
   * 100 exato fez isso no Dashboard e deixou `Math.round` aqui — na tela cujo
   * número vira PDF no R2 como prova de auditoria.
   *
   * E o mesmo PR tornou o defeito COMUM em vez de raro: a fórmula do
   * relatório passou a ser a do Dashboard,
   * `100 × (1 − horas-câmera com violação ÷ (câmeras ativas × horas))`. Numa
   * semana das 17 câmeras da RVB o denominador é 168 × 17 = 2.856
   * horas-câmera, então UMA hora-câmera com violação dá 99,96 e até 14 delas
   * ainda ficam ≥ 99,5 — todas arredondavam para **100**. A mesma semana saía
   * "99" no Dashboard e "100" aqui: o mesmo número, o mesmo produto, duas
   * telas, uma honesta.
   *
   * Troque `scoreImpresso` de volta por `Math.round` e os dois primeiros casos
   * voltam a imprimir 100.
   */
  it('#789 na tela irmã: semana com violação não imprime 100 no relatório', async () => {
    // 1 hora-câmera com violação em 2.856 — o caso comum, não a borda.
    responde({
      data: {
        ...RESPOSTA.data,
        summary: { ...RESPOSTA.data.summary, compliance_rate: 99.96, total_violations: 66 },
      },
    })
    render(<Relatorios />)
    await carregado()
    expect(screen.getByText('99')).toBeTruthy()
    expect(screen.queryByText('100')).toBeNull()
  })

  it('#789 na tela irmã: 99,5 — a borda do arredondamento — também é 99', async () => {
    responde({
      data: {
        ...RESPOSTA.data,
        summary: { ...RESPOSTA.data.summary, compliance_rate: 99.5, total_violations: 13 },
      },
    })
    render(<Relatorios />)
    await carregado()
    expect(screen.getByText('99')).toBeTruthy()
    expect(screen.queryByText('100')).toBeNull()
  })

  it('#789 na tela irmã: 100 exato (zero hora-câmera com violação) segue 100', async () => {
    responde({
      data: {
        ...RESPOSTA.data,
        summary: { ...RESPOSTA.data.summary, compliance_rate: 100, total_violations: 3881 },
      },
    })
    render(<Relatorios />)
    await carregado()
    expect(screen.getByText('100')).toBeTruthy()
  })

  it('agregação que falhou não vira "não tem eventos registrados"', async () => {
    responde({
      data: {
        ...VAZIO.data,
        summary: {
          ...VAZIO.data.summary,
          compliance_rate: null,
          compliance_reason: 'nao_foi_possivel_apurar',
        },
      },
    })
    render(<Relatorios />)
    expect(await screen.findByText(/não foi possível apurar o período/i)).toBeTruthy()
    expect(screen.queryByText(/não tem eventos registrados/i)).toBeNull()
  })

  /**
   * ISSUE #823 — o que o número MEDE, dito na tela.
   *
   * O score é `100 × (1 − horas-câmera com violação ÷ (câmeras ativas ×
   * horas))`, e o denominador SUPÕE que cada câmera ativa foi monitorada o
   * período inteiro. Ninguém mede isso. Com as 17 câmeras da RVB são 408
   * horas-câmera/dia, e a escala inteira vive comprimida no topo: o dia 10/08,
   * com 152 violações concentradas em 31 horas-câmera, sai **92**.
   *
   * "92" sozinho lê-se como "92 % da fábrica está conforme". Não é isso que o
   * número responde. Enquanto a issue não decide o denominador, a leitura
   * honesta é a tela dizer o eixo e mostrar a fração medida — e é isso que
   * `violation_hours`/`camera_hours` (já servidos pelo `_aggregate`) permitem.
   */
  const DIA_DE_152 = {
    data: {
      ...RESPOSTA.data,
      summary: {
        ...RESPOSTA.data.summary,
        compliance_rate: 92.4,
        total_violations: 152,
        violation_hours: 31,
        camera_hours: 408,
      },
    },
  }

  it('#823: a tela diz o EIXO do número — e diz o que ele NÃO é', async () => {
    responde(DIA_DE_152)
    render(<Relatorios />)
    await carregado()

    expect(screen.getByText('92')).toBeTruthy()
    // A MESMA frase do cartão do Dashboard e do rodapé do PDF: o mesmo número
    // com três rótulos diferentes é como ter três números.
    expect(screen.getByText(/% das horas-câmera sem violação/i)).toBeTruthy()
    expect(screen.getByText(/não é % de pessoas em conformidade/i)).toBeTruthy()
  })

  it('#823: a CONTA aparece ao lado do score — 31 de 408, não só "92"', async () => {
    responde(DIA_DE_152)
    render(<Relatorios />)
    await carregado()

    expect(screen.getByText(/horas-câmera do período tiveram violação/i)).toBeTruthy()
    expect(screen.getByText('31')).toBeTruthy()
    expect(screen.getByText('408')).toBeTruthy()
  })

  it('#823: sem denominador servido, a tela não inventa a conta', async () => {
    // Backend antigo (ou score nulo): sem `camera_hours` não houve denominador.
    responde(RESPOSTA)
    render(<Relatorios />)
    await carregado()

    expect(screen.queryByText(/horas-câmera do período tiveram violação/i)).toBeNull()
  })

  /**
   * O travessão sozinho não distingue "nada chegou no período" de "a consulta
   * caiu" — e as duas coisas pedem ações opostas de quem lê. O Dashboard já
   * traduz a razão; esta tela mostrava só "score não apurado".
   */
  it('#823: travessão vem COM a razão — sem câmera ativa não é "sem evento"', async () => {
    responde({
      data: {
        ...RESPOSTA.data,
        summary: {
          ...RESPOSTA.data.summary,
          compliance_rate: null,
          compliance_reason: 'sem_cameras_ativas',
        },
      },
    })
    render(<Relatorios />)
    await carregado()

    expect(screen.getByText('—')).toBeTruthy()
    expect(screen.getByText(/sem câmera ativa para calcular/i)).toBeTruthy()
  })

  it('#823: agregação que caiu diz que caiu, no lugar do número', async () => {
    responde({
      data: {
        ...RESPOSTA.data,
        summary: {
          ...RESPOSTA.data.summary,
          compliance_rate: null,
          compliance_reason: 'nao_foi_possivel_apurar',
        },
      },
    })
    render(<Relatorios />)
    await carregado()

    expect(screen.getByText('—')).toBeTruthy()
    expect(screen.getByText(/a consulta não respondeu/i)).toBeTruthy()
    expect(screen.queryByText(/sem evento no período/i)).toBeNull()
  })

  it('erro mostra o motivo + código e o retry refaz a chamada', async () => {
    let primeira = true
    mocks.get.mockImplementation((rota: string) => {
      if (String(rota).startsWith('/cameras')) return Promise.resolve(CAMERAS)
      if (primeira) {
        primeira = false
        return Promise.reject(new ApiError('boom', 502))
      }
      return Promise.resolve(RESPOSTA)
    })
    render(<Relatorios />)

    expect(await screen.findByText(/o relatório não respondeu \(código 502\)/i)).toBeTruthy()
    expect(screen.queryByText(/\/api\/reports/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    await carregado()
    expect(chamadasDeRelatorio()).toHaveLength(2)
  })
})

describe('intervalo inválido', () => {
  it('não mostra o resumo antigo sob o rótulo do período novo', async () => {
    responde(RESPOSTA)
    render(<Relatorios />)
    await carregado()

    fireEvent.change(screen.getByLabelText('Período'), { target: { value: 'personalizado' } })
    await carregado()
    // "Até" anterior ao "De" padrão (hoje − 7d) — o caso que só a digitação alcança
    fireEvent.change(screen.getByLabelText('Até'), { target: { value: '2020-01-01' } })

    expect(await screen.findByText(/intervalo inválido/i)).toBeTruthy()
    expect(screen.queryByText('cam-04-expedicao')).toBeNull()
    expect(screen.queryByText('31')).toBeNull()
  })
})
