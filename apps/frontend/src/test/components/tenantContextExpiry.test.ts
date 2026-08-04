/**
 * Expiração do contexto de tenant assumido (TTL 30min, core/tenant_context.py).
 *
 * bug liveview-contexto-visivel: o branch 401 de services/api.ts já restaurava
 * o superadmin automaticamente (nunca derrubava pro /login enquanto houvesse
 * backup) — mas TENANT_CONTEXT_META_KEY era apagado por
 * restoreTenantContextBackup ANTES do reload, então o banner pós-reload não
 * sabia de qual tenant era o contexto expirado pra oferecer "Reassumir" (só
 * um toast genérico passageiro). Este teste tranca o contrato: o meta
 * sobrevive em sessionStorage (TENANT_CONTEXT_EXPIRED_META_KEY) pro banner
 * ler depois do reload.
 *
 * localStorage/sessionStorage reais são pouco confiáveis neste ambiente de
 * teste (ver comentário em AppShellTheme.test.tsx — themeStore é mockado de
 * propósito pelo mesmo motivo) — substituídos por um Storage in-memory via
 * vi.stubGlobal, mesma identidade que o módulo sob teste enxerga.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  api,
  TOKEN_KEY,
  TENANT_CONTEXT_BACKUP_KEY,
  TENANT_CONTEXT_META_KEY,
  TENANT_CONTEXT_EXPIRED_FLAG,
  TENANT_CONTEXT_EXPIRED_META_KEY,
} from '../../services/api'

class MemoryStorage implements Storage {
  private store = new Map<string, string>()
  get length(): number { return this.store.size }
  clear(): void { this.store.clear() }
  getItem(key: string): string | null { return this.store.has(key) ? this.store.get(key)! : null }
  key(index: number): string | null { return Array.from(this.store.keys())[index] ?? null }
  removeItem(key: string): void { this.store.delete(key) }
  setItem(key: string, value: string): void { this.store.set(key, String(value)) }
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

describe('api.ts — expiração do contexto de tenant assumido (401)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', new MemoryStorage())
    vi.stubGlobal('sessionStorage', new MemoryStorage())
    // window.location.href = '/x' navega de verdade no jsdom — troca por um
    // objeto que só grava o valor.
    vi.stubGlobal('location', { href: '' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('preserva tenant_id/tenant_name em sessionStorage antes de restaurar o superadmin', async () => {
    // Estado: superadmin assumiu contexto da RVB — token trocado, backup salvo.
    localStorage.setItem(TOKEN_KEY, 'assumed-tenant-token')
    localStorage.setItem(
      TENANT_CONTEXT_BACKUP_KEY,
      JSON.stringify({ token: 'superadmin-token', user: JSON.stringify({ role: 'superadmin' }) }),
    )
    localStorage.setItem(
      TENANT_CONTEXT_META_KEY,
      JSON.stringify({
        tenant_id: 'tenant-rvb',
        tenant_name: 'RVB Isolantes',
        tenant_slug: 'rvb',
        started_at: '2026-08-04T10:00:00Z',
      }),
    )

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(401, { error: 'Token expirado' })),
    )

    await expect(api.get('/cameras')).rejects.toThrow()

    // Meta preservado pro banner ler depois do reload.
    const savedMeta = sessionStorage.getItem(TENANT_CONTEXT_EXPIRED_META_KEY)
    expect(savedMeta).not.toBeNull()
    expect(JSON.parse(savedMeta as string)).toMatchObject({
      tenant_id: 'tenant-rvb',
      tenant_name: 'RVB Isolantes',
    })
    expect(sessionStorage.getItem(TENANT_CONTEXT_EXPIRED_FLAG)).toBe('1')

    // Superadmin restaurado — NUNCA derruba pro /login enquanto houver backup.
    expect(localStorage.getItem(TOKEN_KEY)).toBe('superadmin-token')
    expect(window.location.href).toBe('/admin/tenants')
    expect(window.location.href).not.toBe('/login')

    // Backup consumido — não sobra resíduo pro próximo 401 reprocessar (evita loop).
    expect(localStorage.getItem(TENANT_CONTEXT_BACKUP_KEY)).toBeNull()
    expect(localStorage.getItem(TENANT_CONTEXT_META_KEY)).toBeNull()
  })

  it('sem backup de contexto assumido: 401 cai no logout normal (sem loop)', async () => {
    localStorage.setItem(TOKEN_KEY, 'some-token')

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(401, { error: 'Token expirado' })),
    )

    await expect(api.get('/cameras')).rejects.toThrow()

    expect(window.location.href).toBe('/login')
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(sessionStorage.getItem(TENANT_CONTEXT_EXPIRED_FLAG)).toBeNull()
  })
})
