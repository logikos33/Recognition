/**
 * O que esta tela não pode perder na migração — e o que ela não pode afirmar.
 *
 * Os dois primeiros blocos são o contrato do `DELTA-PRE-MIGRACAO.md §2`: o
 * **badge de procedência** (item 2, ADR-0066) e o **motivo do veredito**
 * (item 5) chegaram na develop dias antes do handoff fechar, custaram caro, e
 * a migração é exatamente o momento em que somem sem ninguém notar — a tela
 * nova "fica linda" e o campo simplesmente não existe mais.
 *
 * O terceiro é a ADR-0067: violação nasce de julgamento POSITIVO de ausência.
 * `GET /api/alerts/:id` não devolve `event_kind`, então a tela não tem como
 * saber se o evento é violação ou conformidade — e por isso NÃO pode escrever
 * a palavra. Um teste, porque "o desenho manda" é justamente o argumento que
 * reintroduz a afirmação errada no próximo PR.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// `vi.hoisted`: o `vi.mock` é ICADO acima das constantes do módulo, então um
// `const` normal ainda não existe quando a fábrica roda.
const { get, post, pode } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  pode: vi.fn(),
}))

vi.mock('../../services/api', async () => {
  // `ApiError` fica REAL: a tela distingue 404 (vazio) de qualquer outro
  // status (erro) por `instanceof`, e um dublê quebraria essa distinção.
  const real = await vi.importActual<Record<string, unknown>>('../../services/api')
  return { ...real, api: { get, post, put: vi.fn(), patch: vi.fn(), delete: vi.fn() } }
})
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => ({ can: pode }) }))
vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<Record<string, unknown>>('react-router-dom')
  return { ...real, useParams: () => ({ id: 'e1' }) }
})

import { ApiError } from '../../services/api'
import { EventoDetalhe, caixaEmPorcento } from './EventoDetalhe'

/** Formato real de `GET /api/alerts/:id` (RVB Isolantes — CAM-04 Expedição). */
const EVENTO = {
  id: 'e1e2e3e4-1111-2222-3333-444455556666',
  camera_id: 'c1',
  camera_name: 'CAM-04 Expedição',
  violations: [
    { class: 'no_helmet', confidence: 0.87, bbox: [100, 50, 200, 400] as [number, number, number, number], bbox_unidade: 'pixels_xywh_frame_original' },
  ],
  acknowledged: false,
  captured_at: '2026-08-25T14:32:08Z',
  created_at: '2026-08-25T14:32:10Z',   // 2s de atraso → contemporâneo
  evidence_url: 'https://r2.example/frame.jpg',
  verification_verdict: null as string | null,
  verified_at: null as string | null,
}

const montar = () => render(<MemoryRouter><EventoDetalhe /></MemoryRouter>)

/** A tela devolve o alerta e, no refetch pós-veredito, o mesmo alerta mudado. */
const responde = (alert: unknown) => get.mockResolvedValue({ data: { alert } })

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({ data: {} })
  pode.mockReset().mockReturnValue(true)
  responde(EVENTO)
})

// ── item 2 do DELTA: badge de procedência (ADR-0066) ────────────────────────

describe('badge de procedência', () => {
  it('carimba "coleta retroativa" quando a gravação atrasou mais que o limiar', async () => {
    responde({ ...EVENTO, captured_at: '2026-08-25T14:32:08Z', created_at: '2026-08-25T15:10:00Z' })
    montar()
    expect(await screen.findByText(/coleta retroativa/i)).toBeTruthy()
  })

  it('NÃO carimba nada quando captura e gravação são contemporâneas', async () => {
    montar()
    // Ausência de badge = ausência de afirmação. Carimbar "AO VIVO" aqui
    // trocaria uma mentira por outra: `alerts.timestamp` ainda nasce com
    // DEFAULT NOW() igual ao created_at nas linhas antigas.
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByText(/coleta retroativa/i)).toBeNull()
    expect(screen.queryByText(/ao vivo/i)).toBeNull()
  })

  it('não afirma nada quando falta uma das duas datas', async () => {
    responde({ ...EVENTO, created_at: null })
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByText(/coleta retroativa/i)).toBeNull()
  })
})

// ── item 5 do DELTA: motivo do veredito ─────────────────────────────────────

describe('motivo do veredito', () => {
  it('o campo existe e vai ao backend como `reason`', async () => {
    montar()
    const campo = await screen.findByLabelText('Motivo do veredito')
    fireEvent.change(campo, { target: { value: 'a caixa pegou a luva do outro' } })
    fireEvent.click(screen.getByRole('button', { name: /descartar/i }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/verification/e1/review', {
      verdict: 'reject',
      reason: 'a caixa pegou a luva do outro',
    })
  })

  it('motivo em branco NÃO manda `reason` — NULL de verdade, não string vazia', async () => {
    montar()
    fireEvent.click(await screen.findByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/verification/e1/review', { verdict: 'approve' })
  })

  it('só espaços também não viram motivo', async () => {
    montar()
    fireEvent.change(await screen.findByLabelText('Motivo do veredito'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/verification/e1/review', { verdict: 'approve' })
  })

  it('o campo limpa depois do veredito, para o próximo não herdar o motivo alheio', async () => {
    montar()
    const campo = await screen.findByLabelText('Motivo do veredito') as HTMLInputElement
    fireEvent.change(campo, { target: { value: 'pessoa de costas' } })
    fireEvent.click(screen.getByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(campo.value).toBe(''))
  })

  it('falha do POST vira aviso na tela, não silêncio', async () => {
    post.mockRejectedValue(new Error('boom'))
    montar()
    fireEvent.click(await screen.findByRole('button', { name: /confirmar/i }))
    expect(await screen.findByRole('alert')).toBeTruthy()
  })
})

// ── ADR-0065 / 0067: o que a tela não pode afirmar ──────────────────────────

describe('veredito exibido', () => {
  it('sem veredito diz a palavra, não só a cor', async () => {
    montar()
    expect(await screen.findByText(/AGUARDA VEREDITO/)).toBeTruthy()
  })

  it('approve vira CONFIRMADO — SEM a palavra "violação" (ADR-0067)', async () => {
    responde({ ...EVENTO, verification_verdict: 'approve', verified_at: '2026-08-25T15:00:00Z' })
    montar()
    expect(await screen.findByText(/CONFIRMADO/)).toBeTruthy()
    // O desenho carimba "VIOLAÇÃO CONFIRMADA". `GET /alerts/:id` não devolve
    // `event_kind`, então a polaridade é desconhecida — e violação nunca nasce
    // do silêncio. Enquanto o campo não vier, a palavra não entra.
    expect(screen.queryByText(/VIOLA[ÇC][ÃA]O/i)).toBeNull()
  })

  it('reject vira DESCARTADO', async () => {
    responde({ ...EVENTO, verification_verdict: 'reject' })
    montar()
    expect(await screen.findByText(/DESCARTADO/)).toBeTruthy()
  })

  it('sem verification:write não mostra botão de veredito nenhum', async () => {
    pode.mockReturnValue(false)
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByRole('button', { name: /confirmar/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /descartar/i })).toBeNull()
    expect(pode).toHaveBeenCalledWith('verification:write')
  })
})

// ── evidência ───────────────────────────────────────────────────────────────

describe('caixa da evidência', () => {
  it('projeta pixels do frame original em % — o mapa da caixa', () => {
    expect(caixaEmPorcento([192, 108, 384, 216], 1920, 1080)).toEqual({
      left: '10%', top: '10%', width: '20%', height: '20%',
    })
  })

  it('bbox de unidade desconhecida não é desenhada, e a tela diz isso', async () => {
    responde({
      ...EVENTO,
      violations: [{ class: 'no_helmet', confidence: 0.9, bbox: [0.1, 0.1, 0.2, 0.2], bbox_unidade: 'normalizado_cxcywh' }],
    })
    montar()
    expect(await screen.findByText(/origem desconhecida/i)).toBeTruthy()
    expect(screen.queryAllByTestId('caixa-violacao')).toHaveLength(0)
  })

  it('evento sem coordenadas mostra o frame e avisa que não há marcação', async () => {
    responde({ ...EVENTO, violations: [{ class: 'no_helmet', confidence: 0.9 }] })
    montar()
    expect(await screen.findByText(/sem coordenadas gravadas/i)).toBeTruthy()
  })

  it('sem evidência a tela continua contando o acontecido', async () => {
    responde({ ...EVENTO, evidence_url: null })
    montar()
    expect(await screen.findByText(/sem imagem de evidência/i)).toBeTruthy()
    expect(screen.getByText('CAM-04 Expedição')).toBeTruthy()
  })
})

// ── os quatro estados da rota (handoff: carregado / loading / vazio / erro) ──

describe('estados', () => {
  it('404 é evento não encontrado — não é erro de carga', async () => {
    get.mockRejectedValue(new ApiError('Alerta não encontrado', 404))
    montar()
    expect(await screen.findByText('Evento não encontrado')).toBeTruthy()
    expect(screen.queryByText(/tentar novamente/i)).toBeNull()
  })

  it('500 é falha de carga, com retry que refaz o GET', async () => {
    get.mockRejectedValueOnce(new ApiError('Erro interno', 500))
    montar()
    // Em `erro` o evento também é null: com a ordem dos branches invertida a
    // tela dizia "Evento não encontrado" para uma falha de rede — mentira que
    // manda o operador embora em vez de oferecer o retry.
    expect(await screen.findByText('Falha ao carregar o evento')).toBeTruthy()
    expect(screen.queryByText('Evento não encontrado')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    responde(EVENTO)
    expect(await screen.findByText('CAM-04 Expedição')).toBeTruthy()
  })

  it('resposta sem alerta cai no vazio, não em tela quebrada', async () => {
    get.mockResolvedValue({ data: {} })
    montar()
    expect(await screen.findByText('Evento não encontrado')).toBeTruthy()
  })
})
