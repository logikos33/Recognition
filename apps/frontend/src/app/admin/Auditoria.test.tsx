/**
 * O que esta tela não pode errar:
 *
 *  · lista via `adminService.getAuditLog`/`exportAuditLog` — NUNCA `fetch`
 *    global direto (o achado do wiring spec era do código antigo; a versão
 *    atual do legado já usa o service, e esta tela reusa o mesmo).
 *  · trocar o período recalcula `date_from` e refaz a busca.
 *  · exportar CSV aciona `downloadBlob` (dentro de `exportAuditLog`), nunca
 *    `window.fetch` cru.
 *  · shape real de `list_audit_log` (`routes.py:2202`) — `{items, total}`,
 *    sem paginação nenhuma quando total ≤ 20.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getAuditLog = vi.fn()
const exportAuditLog = vi.fn()
vi.mock('../../modules/admin/services/adminService', () => ({
  adminService: {
    getAuditLog: (...a: unknown[]) => getAuditLog(...a),
    exportAuditLog: (...a: unknown[]) => exportAuditLog(...a),
  },
}))

// Espiona `fetch` global de propósito: se a tela chamasse alguma rota por
// fora do service mockado (raw fetch), cairia aqui — o service é o único
// jeito de a tela buscar dado neste teste.
const globalFetch = vi.fn()

import { Auditoria } from './Auditoria'

const ENTRADA_REAL = {
  id: 'a1',
  action: 'training_rejected',
  target_type: 'training_job',
  target_id: '11111111-2222-3333-4444-555555555555',
  actor_role: 'superadmin',
  actor_email: 'ana@logikos.com',
  tenant_name: 'RVB Isolantes',
  ip_address: '10.0.0.5',
  created_at: '2026-08-29T14:00:00Z',
}

function montar() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <Auditoria />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getAuditLog.mockReset()
  exportAuditLog.mockReset()
  globalFetch.mockReset()
  vi.stubGlobal('fetch', globalFetch)
})
afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('Auditoria', () => {
  it('carrega via adminService.getAuditLog, nunca fetch global', async () => {
    getAuditLog.mockResolvedValue({ items: [ENTRADA_REAL], total: 1 })
    montar()

    expect(await screen.findByText('training_rejected')).toBeTruthy()
    expect(getAuditLog).toHaveBeenCalledTimes(1)
    expect(globalFetch).not.toHaveBeenCalled()

    // UUID cru nunca aparece na tela — só o prefixo curto, como o legado.
    expect(screen.queryByText(ENTRADA_REAL.target_id)).toBeNull()
    expect(screen.getByText(/11111111/)).toBeTruthy()
  })

  it('trocar o período refaz a busca com date_from recalculado', async () => {
    getAuditLog.mockResolvedValue({ items: [ENTRADA_REAL], total: 1 })
    montar()
    await screen.findByText('training_rejected')

    const chamada1 = getAuditLog.mock.calls[0][0] as { date_from: string }

    fireEvent.change(screen.getByLabelText('Período'), { target: { value: '7d' } })

    await waitFor(() => expect(getAuditLog).toHaveBeenCalledTimes(2))
    const chamada2 = getAuditLog.mock.calls[1][0] as { date_from: string }
    expect(chamada2.date_from).not.toBe(chamada1.date_from)
  })

  it('exportar CSV chama adminService.exportAuditLog, não fetch cru', async () => {
    getAuditLog.mockResolvedValue({ items: [ENTRADA_REAL], total: 1 })
    exportAuditLog.mockResolvedValue(new Blob(['csv'], { type: 'text/csv' }))
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
    montar()
    await screen.findByText('training_rejected')

    fireEvent.click(screen.getByRole('button', { name: /Exportar CSV/ }))

    await waitFor(() => expect(exportAuditLog).toHaveBeenCalledTimes(1))
    expect(globalFetch).not.toHaveBeenCalled()
  })

  it('vazio → EmptyState honesto, sem tabela fantasma', async () => {
    getAuditLog.mockResolvedValue({ items: [], total: 0 })
    montar()
    expect(await screen.findByText('Nenhum registro')).toBeTruthy()
  })

  it('erro → mensagem técnica com a rota real', async () => {
    getAuditLog.mockRejectedValue(new Error('offline'))
    montar()
    expect(await screen.findByText('Não foi possível carregar a auditoria')).toBeTruthy()
    expect(screen.getByText('GET /v1/admin/audit-log')).toBeTruthy()
  })

  it('sem paginação quando total ≤ 20 (não inventa Anterior/Próxima)', async () => {
    getAuditLog.mockResolvedValue({ items: [ENTRADA_REAL], total: 1 })
    montar()
    await screen.findByText('training_rejected')
    expect(screen.queryByText(/Anterior/)).toBeNull()
    expect(screen.queryByText(/Próxima/)).toBeNull()
  })
})
