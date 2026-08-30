/**
 * O que esta tela não pode errar:
 *
 *  · GET é `/modules/epi/classes` (o mesmo do antigo) — a resposta vem no
 *    envelope `{data:{classes}}`, não `classes` na raiz;
 *  · POST /classes leva o payload certo (nome, cor, módulo);
 *  · a polaridade nunca vira booleano binário na tela — o PATCH manda
 *    `is_violation`, e se o valor enviado for o INVERSO do clicado, o teste
 *    de baixo tem de quebrar (mutação verificada manualmente ao escrever);
 *  · DELETE 409 chega legível (a API já manda a frase pronta) — não pode
 *    sumir em silêncio.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn()
const post = vi.fn()
const patch = vi.fn()
const del = vi.fn()
vi.mock('../../services/api', () => ({
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    patch: (...a: unknown[]) => patch(...a),
    delete: (...a: unknown[]) => del(...a),
  },
}))

const toastOk = vi.fn()
const toastErro = vi.fn()
vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => ({ success: toastOk, error: toastErro, warning: vi.fn(), info: vi.fn() }),
}))

import { Classes } from './Classes'
import { VALORES } from '../tokens/lk.css'

const tenantClasse = (extra: Record<string, unknown> = {}) => ({
  id: 7,
  class_id: 100007,
  class_name: 'capacete',
  display_name: 'Capacete',
  color: '#3ECF8E',
  source: 'tenant' as const,
  archived_at: null,
  display_order: 0,
  usage_count: 40,
  polaridade: 'conformidade' as const,
  ...extra,
})

const catalogoClasse = (extra: Record<string, unknown> = {}) => ({
  id: 1,
  class_id: 1,
  class_name: 'no_gloves',
  display_name: 'Sem luva',
  color: '#e5484d',
  source: 'module' as const,
  is_active: true,
  usage_count: 12,
  polaridade: 'violacao' as const,
  ...extra,
})

const responde = (classes: unknown[]) => get.mockResolvedValue({ data: { classes } })

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({ data: { class_id: 99 } })
  patch.mockReset().mockResolvedValue({ data: {} })
  del.mockReset().mockResolvedValue({ data: {} })
  toastOk.mockReset()
  toastErro.mockReset()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

describe('Classes (Estúdio)', () => {
  it('lista renderiza: classes do tenant e catálogo, cada uma na sua seção', async () => {
    responde([tenantClasse(), catalogoClasse()])
    render(<Classes />)
    expect(await screen.findByText('Capacete')).toBeTruthy()
    expect(screen.getByText('Sem luva')).toBeTruthy()
    expect(get).toHaveBeenCalledWith('/modules/epi/classes?include_archived=1')
  })

  it('criar chama POST /classes com o payload certo', async () => {
    responde([tenantClasse()])
    render(<Classes />)
    await screen.findByText('Capacete')
    fireEvent.change(screen.getByPlaceholderText(/nova classe/i), { target: { value: 'Luva' } })
    fireEvent.click(screen.getByRole('button', { name: /nova classe/i }))
    expect(post).toHaveBeenCalledWith('/classes', {
      name: 'Luva',
      color: VALORES.cianoVisao,
      module_code: 'epi',
    })
  })

  it('polaridade edita via PATCH is_violation — NÃO um booleano inventado na UI', async () => {
    responde([tenantClasse({ polaridade: 'conformidade' })])
    render(<Classes />)
    await screen.findByText('Capacete')
    fireEvent.click(screen.getByRole('button', { name: 'Violação' }))
    // Mutação verificada: trocar para `is_violation: false` aqui quebra o
    // teste (o clique foi em "Violação", não em "Conformidade").
    expect(patch).toHaveBeenCalledWith('/classes/7', { is_violation: true })
  })

  it('excluir com 409 mostra o erro legível do backend — não silencioso', async () => {
    responde([tenantClasse({ archived_at: '2026-08-01T00:00:00Z' })])
    del.mockRejectedValue(new Error('Classe possui 3 anotações vinculadas — arquive a classe em vez de excluir'))
    render(<Classes />)
    fireEvent.click(await screen.findByRole('button', { name: /arquivadas/i }))
    fireEvent.click(screen.getByRole('button', { name: /excluir/i }))
    expect(del).toHaveBeenCalledWith('/classes/7')
    await waitFor(() =>
      expect(toastErro).toHaveBeenCalledWith(
        'Classe possui 3 anotações vinculadas — arquive a classe em vez de excluir',
      ),
    )
    expect(screen.getByText('Capacete')).toBeTruthy() // ainda na tela: 409 não some em silêncio
  })

  it('sem nenhuma classe, o vazio mostra CTA para criar a primeira', async () => {
    responde([])
    render(<Classes />)
    expect(await screen.findByText(/nenhuma classe cadastrada/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /nova classe/i })).toBeTruthy()
  })
})
