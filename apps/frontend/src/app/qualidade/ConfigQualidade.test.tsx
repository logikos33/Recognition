/**
 * O que esta tela não pode errar:
 *
 *  · inventar o ponto de inspeção que o backend não tem (P1, critério,
 *    tolerância, INFO-038) só porque o desenho o mostra;
 *  · oferecer ação sem rota, ou — pior — ação COM rota que grava um número que
 *    ninguém lê e responde "salvo";
 *  · imprimir UUID de câmera como se fosse nome;
 *  · repetir a legenda do desenho ("sem deploy"), que é falsa para limiar.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ can: vi.fn((_p: string) => true) }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

const get = vi.fn()
vi.mock('../../services/api', () => ({ api: { get: (...a: unknown[]) => get(...a) } }))

import { ConfigQualidade } from './ConfigQualidade'
import * as s from './ConfigQualidade.css'

/** Cabeçalhos REAIS da tabela de estações — a lista que o servidor sustenta. */
const cabecalhos = (container: HTMLElement) =>
  Array.from(container.querySelectorAll(`.${s.th}`)).map((e) => e.textContent?.trim())

const CAM_UUID = '9f1d4d5e-2b7a-4b0e-9a11-6c0f7d3c8e21'
const CAM_ORFA = 'aa11bb22-cc33-dd44-ee55-ff6677889900'

/** Forma REAL de `{tenant_schema}.quality_stations` (o GET faz SELECT *). */
const estacao = (extra: Record<string, unknown> = {}) => ({
  id: 'est-1',
  station_code: 'EST-01',
  name: 'Estação 1 — Anéis',
  description: null,
  camera_ids: [CAM_UUID],
  is_active: true,
  ...extra,
})

/** Forma REAL de `GET /v1/quality/cameras`. */
const camera = (extra: Record<string, unknown> = {}) => ({
  id: CAM_UUID,
  name: 'Bancada Anéis 01',
  location: 'Galpão B',
  ok_confidence_threshold: 0.6,
  nok_confidence_threshold: 0.45,
  ...extra,
})

const responde = (stations: unknown[], cameras: unknown[], disponiveis: unknown[] = []) =>
  get.mockImplementation((rota: string) => {
    const r = String(rota)
    if (r.includes('/gate/stations')) return Promise.resolve({ data: { stations } })
    if (r.includes('/cameras/available')) return Promise.resolve({ data: { cameras: disponiveis } })
    return Promise.resolve({ data: { cameras } })
  })

const abrirC2 = () => fireEvent.click(screen.getByRole('tab', { name: /limiares/i }))

beforeEach(() => {
  get.mockReset()
  auth.can.mockReset().mockReturnValue(true)
})

describe('configuração da qualidade — aba C1 (pontos & rotas)', () => {
  it('não inventa ponto de inspeção: diz que o objeto não existe no servidor', async () => {
    responde([estacao()], [camera()])
    render(<ConfigQualidade />)
    expect(await screen.findByText(/ainda não existe no servidor/i)).toBeTruthy()
    // Nada do desenho que pende do ponto pode aparecer.
    expect(screen.queryByText('P1')).toBeNull()
    expect(screen.queryByText(/INFO-0\d\d/)).toBeNull()
    expect(screen.queryByText(/Transpasse da cordoalha/i)).toBeNull()
  })

  it('"Novo ponto" fica no lugar do desenho, DESABILITADO e dizendo por quê', async () => {
    responde([estacao()], [camera()])
    render(<ConfigQualidade />)
    const b = (await screen.findByRole('button', { name: /novo ponto/i })) as HTMLButtonElement
    expect(b.disabled).toBe(true)
    expect(b.title).toMatch(/sem rota|não existe/i)
  })

  it('"PUBLICAR ALTERAÇÃO" também fica desabilitado — não há o que publicar', async () => {
    responde([estacao()], [camera()])
    render(<ConfigQualidade />)
    const b = (await screen.findByRole('button', { name: /publicar/i })) as HTMLButtonElement
    expect(b.disabled).toBe(true)
    expect(b.title).toMatch(/ponto de inspeção/i)
  })
})

describe('configuração da qualidade — aba C2 (limiares & estações)', () => {
  it('lista as estações que o servidor devolve, com o NOME da câmera', async () => {
    responde([estacao()], [camera()])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    expect(await screen.findByText('Estação 1 — Anéis')).toBeTruthy()
    // O nome aparece duas vezes de propósito: na linha de limiar e na célula da
    // estação. O que não pode aparecer nenhuma vez é o identificador.
    expect(screen.getAllByText('Bancada Anéis 01').length).toBeGreaterThan(0)
    // UUID cru na tela é proibido — é a terceira vez que este defeito aparece.
    expect(screen.queryByText(new RegExp(CAM_UUID, 'i'))).toBeNull()
  })

  it('câmera que não resolve por nome NÃO vira UUID na célula', async () => {
    responde([estacao({ camera_ids: [CAM_ORFA] })], [camera()])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    expect(await screen.findByText(/câmera não identificada/i)).toBeTruthy()
    expect(screen.queryByText(new RegExp(CAM_ORFA, 'i'))).toBeNull()
  })

  it('mostra os dois limiares REAIS (por câmera), não as três faixas do desenho', async () => {
    responde([estacao()], [camera()])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    expect(await screen.findByText('0,60')).toBeTruthy()
    expect(screen.getByText('0,45')).toBeTruthy()
    // "dúvida" não existe em tabela, rota nem worker — o caminho é binário.
    // Só a explicação pode citar a palavra; nenhuma faixa pode ser rotulada com ela.
    expect(screen.queryByText('dúvida')).toBeNull()
    expect(screen.getByText(/caminho servido é binário/i)).toBeTruthy()
  })

  it('limiar não gravado diz "não definido" — não vira 0,00', async () => {
    responde([estacao()], [camera({ ok_confidence_threshold: null })])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    expect(await screen.findByText(/não definido/i)).toBeTruthy()
    expect(screen.queryByText('0,00')).toBeNull()
  })

  it('"Editar limiar" fica desabilitado: a rota grava, mas ninguém lê o valor', async () => {
    responde([estacao()], [camera()])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    const b = (await screen.findByRole('button', {
      name: /editar limiar/i,
    })) as HTMLButtonElement
    expect(b.disabled).toBe(true)
    expect(b.title).toMatch(/QUALITY_VOTING_THRESHOLD/)
  })

  it('não repete a legenda falsa do desenho ("sem deploy")', async () => {
    responde([estacao()], [camera()])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    expect(screen.queryByText(/sem deploy/i)).toBeNull()
  })

  it('não mostra colunas que o servidor não tem: token e pontos atendidos', async () => {
    responde([estacao()], [camera()])
    const { container } = render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    await screen.findByText('Estação 1 — Anéis')
    // A tabela só pode ter as colunas que o servidor sustenta. (A faixa de
    // lacuna abaixo dela CITA as que faltam — citar não é exibir.)
    expect(cabecalhos(container)).toEqual(['Estação', 'Câmera', 'Situação'])
    expect(screen.queryByText(/••••/)).toBeNull()
    expect(screen.queryByRole('link', { name: /regenerar/i })).toBeNull()
  })

  it('situação da estação é cor + ícone + PALAVRA, e somente leitura', async () => {
    responde([estacao({ is_active: false })], [camera()])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    const estado = await screen.findByText('INATIVA')
    expect(estado.getAttribute('title')).toMatch(/nenhuma rota grava/i)
  })

  it('sem estação, o vazio é honesto e não promete cadastro que não foi desenhado', async () => {
    responde([], [camera()])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    expect(await screen.findByText(/nenhuma estação cadastrada/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /nova estação/i })).toBeNull()
  })

  it('sem câmera no módulo, o vazio de limiares também é honesto', async () => {
    responde([estacao()], [])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    expect(await screen.findByText(/nenhuma câmera atribuída/i)).toBeTruthy()
  })
})

describe('configuração da qualidade — estados de carga', () => {
  it('erro mostra a rota e o retry refaz a chamada', async () => {
    get.mockRejectedValue(new Error('timeout'))
    render(<ConfigQualidade />)
    expect(await screen.findByText(/GET \/api\/v1\/quality\/gate\/stations/)).toBeTruthy()
    responde([estacao()], [camera()])
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    expect(await screen.findByRole('tab', { name: /limiares/i })).toBeTruthy()
  })

  it('a faixa de lacuna dos limiares só aparece para quem pode configurar', async () => {
    auth.can.mockReturnValue(false)
    responde([estacao()], [camera()])
    render(<ConfigQualidade />)
    await screen.findByRole('tab', { name: /limiares/i })
    abrirC2()
    await screen.findByText('Estação 1 — Anéis')
    expect(screen.queryByText(/travado de propósito/i)).toBeNull()
  })
})
