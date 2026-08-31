/**
 * O que esta tela não pode errar: prometer que pausou sem endpoint,
 * inventar hora do último aviso, mostrar jargão de motor pro cliente, ou
 * deixar o modo avançado visível pra quem não cuida da plataforma.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({
  permissoes: ['cameras:configure'] as string[],
  superadmin: false,
  ApiErroFalso: class ApiErroFalso extends Error {
    status: number
    constructor(status: number) {
      super(`HTTP ${status}`)
      this.status = status
    }
  },
}))

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => h.permissoes.includes(p), isSuperAdmin: h.superadmin }),
}))

// A miniatura ao vivo é detalhe de outra tela — aqui só precisa não quebrar.
vi.mock('../../hooks/useCameraSnapshot', () => ({
  useCameraSnapshot: () => ({
    status: 'idle', url: null, capturedAt: null, errorReason: null, loading: false, timedOut: false,
    refresh: vi.fn(),
  }),
}))

const get = vi.fn()
const post = vi.fn()
const put = vi.fn()
const del = vi.fn()

vi.mock('../../services/api', () => ({
  ApiError: h.ApiErroFalso,
  api: {
    get: (...a: unknown[]) => get(...(a as [string])),
    post: (...a: unknown[]) => post(...(a as [string, unknown?])),
    put: (...a: unknown[]) => put(...(a as [string, unknown?])),
    delete: (...a: unknown[]) => del(...(a as [string])),
  },
}))

import { Cenario } from './Cenario'

const CAMERA_ID = 'cam-1'

const CLASSES = [
  { class_name: 'capacete', display_name: 'Capacete' },
  { class_name: 'colete', display_name: 'Colete refletivo' },
]

/** Config REAL de `epi_zone.py` — zone_points + watch_classes. */
const opEpi = (extra: Record<string, unknown> = {}) => ({
  id: 1,
  camera_id: CAMERA_ID,
  module_id: 'mod-epi',
  type_id: 'epi_zone',
  template_id: 'epi',
  name: 'Doca 3',
  status: 'active',
  config: {
    zone_points: [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
    watch_classes: ['capacete'],
  },
  ...extra,
})

function servir(ops: unknown[]) {
  get.mockImplementation((path: string) => {
    if (path.includes('/operations')) return Promise.resolve({ data: { operations: ops } })
    if (path.startsWith('/modules/') && path.includes('/classes')) {
      return Promise.resolve({ data: { classes: CLASSES } })
    }
    if (path === '/modules/') return Promise.resolve({ data: { modules: [{ id: 'mod-epi', module_code: 'epi' }] } })
    if (path === `/cameras/${CAMERA_ID}`) {
      return Promise.resolve({ data: { id: CAMERA_ID, name: 'CAM-04 Expedição', active_module: 'epi' } })
    }
    return Promise.resolve({ data: {} })
  })
}

function montar() {
  return render(
    <MemoryRouter initialEntries={[`/novo/epi/cameras/${CAMERA_ID}/cenario`]}>
      <Routes>
        <Route path="/novo/epi/cameras/:cameraId/cenario" element={<Cenario />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function abrirTemplateEpi() {
  fireEvent.click(await screen.findByRole('button', { name: /desenhar nova regra/i }))
  fireEvent.click(await screen.findByRole('button', { name: /zona de epi obrigatório/i }))
  await screen.findByPlaceholderText(/nome deste lugar/i)
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  put.mockReset()
  del.mockReset()
  post.mockResolvedValue({ data: { operation: opEpi() } })
  h.permissoes = ['cameras:configure']
  h.superadmin = false
})

describe('lista', () => {
  it('renderiza a regra real, com a frase em linguagem de gente e o último aviso', async () => {
    servir([opEpi({ last_event_at: '2026-08-29T14:32:00Z' })])
    montar()
    expect(await screen.findByText('Doca 3')).toBeTruthy()
    expect(screen.getByText('Você verá um evento quando alguém entrar em "Doca 3" sem capacete.')).toBeTruthy()
    expect(screen.getByText(/ÚLTIMO AVISO/)).toBeTruthy()
  })

  it('sem último disparo, o cartão OMITE a linha — nunca inventa hora', async () => {
    servir([opEpi({ last_event_at: null })])
    montar()
    await screen.findByText('Doca 3')
    expect(screen.queryByText(/ÚLTIMO AVISO/)).toBeNull()
  })

  it('vazio honesto quando a câmera ainda não vigia nada', async () => {
    servir([])
    montar()
    expect(await screen.findByText(/esta câmera ainda não vigia nada/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /desenhe sua primeira zona/i })).toBeTruthy()
  })
})

describe('editor — template primeiro', () => {
  it('escolher o template pré-desenha a geometria e só habilita salvar com os 3 passos', async () => {
    servir([])
    montar()
    await abrirTemplateEpi()

    // geometria padrão da área (4 cantos) já entra pré-desenhada
    expect(screen.getByText(/4 cantos na zona/i)).toBeTruthy()

    const salvarIncompleto = screen.getByRole('button', { name: /complete os 3 passos/i })
    expect((salvarIncompleto as HTMLButtonElement).disabled).toBe(true)

    fireEvent.change(screen.getByPlaceholderText(/nome deste lugar/i), { target: { value: 'Doca 3' } })
    expect(screen.getByRole('button', { name: /complete os 3 passos/i })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Capacete' }))

    const salvarCompleto = await screen.findByRole('button', { name: /salvar e começar a valer/i })
    expect((salvarCompleto as HTMLButtonElement).disabled).toBe(false)
  })

  it('o preview em linguagem natural muda a cada edição', async () => {
    servir([])
    montar()
    await abrirTemplateEpi()

    fireEvent.change(screen.getByPlaceholderText(/nome deste lugar/i), { target: { value: 'Doca 3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Capacete' }))
    expect(
      await screen.findByText('Você verá um evento quando alguém entrar em "Doca 3" sem capacete.'),
    ).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /só avisar se ficar um tempo dentro/i }))
    expect(
      await screen.findByText(/Você verá um evento quando alguém ficar mais de \d+ segundos em "Doca 3" sem capacete\./),
    ).toBeTruthy()
  })
})

describe('pausar/retomar — degradação graciosa', () => {
  it('funciona de ponta a ponta quando a rota responde', async () => {
    servir([opEpi()])
    post.mockResolvedValue({ data: { operation: opEpi({ status: 'inactive' }) } })
    montar()
    const pausar = await screen.findByRole('button', { name: 'Pausar' })
    fireEvent.click(pausar)
    expect(await screen.findByRole('button', { name: 'Retomar' })).toBeTruthy()
    expect(post).toHaveBeenCalledWith(`/operations/1/pause`)
  })

  it('rota ainda sem deploy (404/405) vira selo de dependência, sem quebrar a tela', async () => {
    servir([opEpi()])
    post.mockRejectedValue(new h.ApiErroFalso(404))
    montar()
    const pausar = await screen.findByRole('button', { name: 'Pausar' })
    fireEvent.click(pausar)

    const dependente = await screen.findByTitle(/depende do pedido b1/i)
    expect((dependente as HTMLButtonElement).disabled).toBe(true)
    // a tela segue inteira — nada quebrou
    expect(screen.getByText('Doca 3')).toBeTruthy()
  })
})

describe('modo avançado — só superadmin', () => {
  it('fica invisível para quem não é superadmin', async () => {
    h.superadmin = false
    servir([])
    montar()
    await abrirTemplateEpi()
    expect(screen.queryByText(/modo avançado/i)).toBeNull()
  })

  it('aparece para superadmin', async () => {
    h.superadmin = true
    servir([])
    montar()
    await abrirTemplateEpi()
    expect(await screen.findByText(/modo avançado/i)).toBeTruthy()
  })
})

describe('linguagem', () => {
  const PROIBIDAS = [
    /\bthreshold\b/i, /\biou\b/i, /condition_satisfied/i, /bounding box/i, /\boverlap\b/i,
    /\bpolygon\b/i, /\bpayload\b/i, /\bjson\b/i, /confidence score/i, /infer[êe]ncia/i,
    /\byolo\b/i, /\btracker\b/i,
  ]

  it('zero jargão proibido no texto renderizado (lista + editor, sessão de cliente)', async () => {
    h.superadmin = false
    servir([opEpi()])
    const { container } = montar()
    await screen.findByText('Doca 3')
    fireEvent.click(screen.getByRole('button', { name: /editar/i }))
    await screen.findByPlaceholderText(/nome deste lugar/i)

    const texto = container.textContent ?? ''
    for (const proibida of PROIBIDAS) {
      expect(texto, `achou "${proibida}" no texto renderizado`).not.toMatch(proibida)
    }
  })
})

describe('avaliação e simulação — nunca fingem', () => {
  it('avaliação OK/NOK fica desabilitada com o selo do pedido B2', async () => {
    servir([opEpi()])
    montar()
    await screen.findByText('Doca 3')
    const sim = screen.getByRole('button', { name: /sim, está boa/i })
    const nao = screen.getByRole('button', { name: /não, precisa ajuste/i })
    expect((sim as HTMLButtonElement).disabled).toBe(true)
    expect((nao as HTMLButtonElement).disabled).toBe(true)
  })

  it('simular sobre a cena fica desabilitado com o selo do pedido B6', async () => {
    servir([])
    montar()
    await abrirTemplateEpi()
    const simular = screen.getByRole('button', { name: /simular sobre a cena/i })
    expect((simular as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('sem permissão', () => {
  it('a lista continua visível, mas editar/desenhar somem', async () => {
    h.permissoes = []
    servir([opEpi()])
    montar()
    await screen.findByText('Doca 3')
    expect(screen.queryByRole('button', { name: /desenhar nova regra/i })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Editar' })).toBeNull()
  })

})
