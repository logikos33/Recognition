/**
 * O que esta tela não pode errar: oferecer ação que o servidor não tem, e
 * inventar rótulo para estado que ninguém documentou.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ can: vi.fn((_p: string) => true) }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

const get = vi.fn()
vi.mock('../../services/api', () => ({ api: { get: (...a: unknown[]) => get(...a) } }))

import { Operacoes } from './Operacoes'

/** Campos REAIS de `operations` (operation_repository.py:24-26). */
const op = (id: number, extra: Record<string, unknown> = {}) => ({
  id,
  camera_id: 'cam-1',
  module_id: MODULO_UUID,
  type_id: 'ppe_zone',
  name: `Operação ${id}`,
  status: 'active',
  version: 3,
  last_evaluated_at: '2026-08-29T14:32:00Z',
  ...extra,
})

/**
 * Formas REAIS, medidas no DEV: `/cameras/<id>` devolve a câmera DIRETO em
 * `data` (não aninhada), e `module_id` da operação é um UUID que casa com
 * `modules[].id`.
 */
const MODULO_UUID = 'c925cab6-ed2b-43bb-8b4b-d1fd51b176f4'
const responde = (ops: unknown[]) =>
  get.mockImplementation((rota: string) => {
    const r = String(rota)
    if (r.includes('/operations')) return Promise.resolve({ data: { operations: ops } })
    if (r.startsWith('/modules'))
      return Promise.resolve({ data: { modules: [{ id: MODULO_UUID, module_code: 'epi' }] } })
    return Promise.resolve({ data: { id: 'cam-1', name: 'Entrada Expedição' } })
  })

const montar = () =>
  render(
    <MemoryRouter initialEntries={['/novo/epi/cameras/cam-1/operations']}>
      <Routes>
        <Route path="/novo/epi/cameras/:cameraId/operations" element={<Operacoes />} />
      </Routes>
    </MemoryRouter>,
  )

beforeEach(() => {
  get.mockReset()
  auth.can.mockReset().mockReturnValue(true)
})

describe('operações da câmera', () => {
  it('lista o que o servidor devolve, com o nome da câmera no título', async () => {
    responde([op(1), op(2, { name: 'Contagem da doca' })])
    montar()
    expect(await screen.findByText('Entrada Expedição')).toBeTruthy()
    expect(screen.getByText('Contagem da doca')).toBeTruthy()
  })

  it('Pausar existe no lugar do desenho, mas DESABILITADO — não há rota', async () => {
    // PUT /operations/<id> aceita só name e config; o status é escrito pelo
    // worker. Oferecer o botão ativo seria prometer o que não acontece.
    responde([op(1)])
    montar()
    const pausar = (await screen.findByRole('button', { name: 'Pausar' })) as HTMLButtonElement
    expect(pausar.disabled).toBe(true)
    expect(pausar.title).toMatch(/name e config|worker/i)
  })

  it('Avaliações também fica desabilitado — não há onde guardar o julgamento', async () => {
    responde([op(1)])
    montar()
    const aval = (await screen.findByRole('button', { name: 'Avaliações' })) as HTMLButtonElement
    expect(aval.disabled).toBe(true)
  })

  it('status desconhecido NÃO vira rótulo bonito', async () => {
    // O enum de status não está publicado no contrato. Inventar "rodando" para
    // um valor que ninguém documentou é afirmar o que não se sabe.
    responde([op(1, { status: 'algo_novo_do_worker' })])
    montar()
    expect(await screen.findByText('SEM SINAL')).toBeTruthy()
    expect(screen.queryByText('RODANDO')).toBeNull()
  })

  it('operação nunca avaliada diz isso — não inventa data', async () => {
    responde([op(1, { last_evaluated_at: null })])
    montar()
    expect(await screen.findByText('NUNCA AVALIADA')).toBeTruthy()
  })

  it('sem operação, o vazio é honesto e não promete criação que não existe', async () => {
    responde([])
    montar()
    expect(await screen.findByText(/ainda não vigia nada/i)).toBeTruthy()
    // O desenho traz "Nova operação"; o formulário não foi desenhado.
    expect(screen.queryByRole('button', { name: /nova operação/i })).toBeNull()
  })

  it('erro mostra a rota e o retry refaz a chamada', async () => {
    get.mockRejectedValue(new Error('timeout'))
    montar()
    expect(await screen.findByText(/GET \/api\/cameras\/cam-1\/operations/)).toBeTruthy()
    responde([op(1)])
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    expect(await screen.findByText('Operação 1')).toBeTruthy()
  })

  it('leva ao cenário DENTRO do front novo', async () => {
    responde([op(1)])
    montar()
    const link = await screen.findByRole('link', { name: /editar zonas/i })
    expect(link.getAttribute('href')).toBe('/novo/epi/cameras/cam-1/scenario')
  })

  it('não mostra UUID cru: resolve o módulo pelo código, ou omite', async () => {
    // `module_id` é UUID. Sem resolver, a linha mostrava
    // "MÓDULO C925CAB6-ED2B-…" — dado ilegível, o mesmo defeito do "Top câmera".
    responde([op(1)])
    montar()
    expect(await screen.findByText(/MÓDULO EPI/)).toBeTruthy()
    expect(screen.queryByText(new RegExp(MODULO_UUID, 'i'))).toBeNull()
  })

  it('módulo que não resolve simplesmente não entra na linha', async () => {
    responde([op(1, { module_id: 'uuid-que-nao-existe' })])
    montar()
    expect(await screen.findByText(/TIPO ppe_zone/)).toBeTruthy()
    expect(screen.queryByText(/MÓDULO/)).toBeNull()
  })
})
