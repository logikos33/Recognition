/**
 * scheduleTenantContextRenewal / cancelTenantContextRenewal (D-48, opção C).
 *
 * O token de contexto assumido tem TTL curto (30min, TENANT_CONTEXT_TTL_MINUTES
 * em app/core/tenant_context.py). Sem renovação proativa, uma sessão de
 * trabalho mais longa cairia no meio (branch 401 restaura o superadmin —
 * services/api.ts). Este teste tranca: dispara ~5min antes do TTL (25min),
 * troca o token SEM reload, reagenda em caso de sucesso, e NÃO reagenda em
 * caso de falha (deixa expirar naturalmente).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, TOKEN_KEY, TENANT_CONTEXT_META_KEY } from '../../services/api'
import { cancelTenantContextRenewal, scheduleTenantContextRenewal } from '../../services/tenantContext'

vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof import('../../services/api')>('../../services/api')
  return { ...actual, api: { ...actual.api, post: vi.fn() } }
})

// localStorage real é pouco confiável neste ambiente de teste (mesmo motivo
// documentado em tenantContextExpiry.test.ts) — substituído por um Storage
// in-memory via vi.stubGlobal.
class MemoryStorage implements Storage {
  private store = new Map<string, string>()
  get length(): number { return this.store.size }
  clear(): void { this.store.clear() }
  getItem(key: string): string | null { return this.store.has(key) ? this.store.get(key)! : null }
  key(index: number): string | null { return Array.from(this.store.keys())[index] ?? null }
  removeItem(key: string): void { this.store.delete(key) }
  setItem(key: string, value: string): void { this.store.set(key, String(value)) }
}

// TENANT_CONTEXT_TTL_MINUTES (30) - RENEW_BEFORE_EXPIRY_MINUTES (5), espelhado
// de services/tenantContext.ts (não exportado — cálculo replicado aqui).
const RENEW_DELAY_MS = (30 - 5) * 60_000

function activateContext(tenantId = 'tenant-rvb'): void {
  localStorage.setItem(
    TENANT_CONTEXT_META_KEY,
    JSON.stringify({
      tenant_id: tenantId,
      tenant_name: 'RVB Isolantes',
      tenant_slug: 'rvb',
      started_at: new Date().toISOString(),
    }),
  )
}

function renewResponse(token: string) {
  return {
    status: 'success',
    data: {
      token,
      tenant: { id: 'tenant-rvb' },
      user: { role: 'superadmin' },
      expires_in_minutes: 30,
    },
  }
}

describe('scheduleTenantContextRenewal', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', new MemoryStorage())
    vi.stubGlobal('sessionStorage', new MemoryStorage())
    vi.mocked(api.post).mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    cancelTenantContextRenewal()
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('sem contexto ativo: não agenda nada — renew nunca é chamado', async () => {
    scheduleTenantContextRenewal()

    await vi.advanceTimersByTimeAsync(RENEW_DELAY_MS + 60_000)

    expect(api.post).not.toHaveBeenCalled()
  })

  it('em contexto ativo: renova ~5min antes do TTL, trocando o token sem reload', async () => {
    activateContext()
    vi.mocked(api.post).mockResolvedValue(renewResponse('renewed-token-1'))

    scheduleTenantContextRenewal()
    // Não dispara antes da hora.
    expect(api.post).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(RENEW_DELAY_MS)

    expect(api.post).toHaveBeenCalledWith('/v1/admin/tenant-context/renew', {})
    expect(localStorage.getItem(TOKEN_KEY)).toBe('renewed-token-1')
  })

  it('sucesso reagenda a próxima renovação — sessão longa continua renovando', async () => {
    activateContext()
    vi.mocked(api.post)
      .mockResolvedValueOnce(renewResponse('renewed-token-1'))
      .mockResolvedValueOnce(renewResponse('renewed-token-2'))

    scheduleTenantContextRenewal()

    await vi.advanceTimersByTimeAsync(RENEW_DELAY_MS)
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem(TOKEN_KEY)).toBe('renewed-token-1')

    await vi.advanceTimersByTimeAsync(RENEW_DELAY_MS)
    expect(api.post).toHaveBeenCalledTimes(2)
    expect(localStorage.getItem(TOKEN_KEY)).toBe('renewed-token-2')
  })

  it('falha no renew: NÃO reagenda — deixa expirar naturalmente (401 restaura o superadmin)', async () => {
    activateContext()
    vi.mocked(api.post).mockRejectedValue(new Error('Contexto assumido encerrado (token expirou)'))

    scheduleTenantContextRenewal()

    await vi.advanceTimersByTimeAsync(RENEW_DELAY_MS)
    expect(api.post).toHaveBeenCalledTimes(1)

    // Mais um ciclo inteiro se passa — nenhuma nova tentativa agendada.
    await vi.advanceTimersByTimeAsync(RENEW_DELAY_MS * 2)
    expect(api.post).toHaveBeenCalledTimes(1)
  })

  it('cancelTenantContextRenewal impede a renovação agendada de disparar', async () => {
    activateContext()
    vi.mocked(api.post).mockResolvedValue(renewResponse('renewed-token-1'))

    scheduleTenantContextRenewal()
    cancelTenantContextRenewal()

    await vi.advanceTimersByTimeAsync(RENEW_DELAY_MS + 60_000)

    expect(api.post).not.toHaveBeenCalled()
  })

  it('reagendar (assumir de novo) cancela qualquer timer pendente anterior', async () => {
    activateContext()
    vi.mocked(api.post).mockResolvedValue(renewResponse('renewed-token-1'))

    scheduleTenantContextRenewal()
    scheduleTenantContextRenewal() // idempotente — não deve duplicar o timer

    await vi.advanceTimersByTimeAsync(RENEW_DELAY_MS)

    expect(api.post).toHaveBeenCalledTimes(1)
  })
})
