/**
 * Serviço de API centralizado.
 *
 * LIÇÃO V1: Token SEMPRE pela mesma chave ('token').
 * LIÇÃO V1: Timeout em todas as requests (15s).
 * LIÇÃO V1: Sem dependência de objeto api.logout() externo.
 */
export const TOKEN_KEY = 'token'

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t)
export const removeToken = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('user')
}

// ── Impersonation "ver como" (WS6) ──────────────────────────────────────────
// Chaves vivem aqui (e não em impersonation.ts) para o branch 401 abaixo
// restaurar o superadmin sem import circular.
export const IMPERSONATION_BACKUP_KEY = 'impersonation_backup'
export const IMPERSONATION_META_KEY = 'impersonation'
export const IMPERSONATION_EXPIRED_FLAG = 'impersonation_expired'

/**
 * Restaura a sessão original do superadmin a partir do backup salvo ao
 * iniciar uma visualização "ver como". Retorna true se havia backup.
 */
export function restoreImpersonationBackup(redirect = '/admin/tenants'): boolean {
  const raw = localStorage.getItem(IMPERSONATION_BACKUP_KEY)
  localStorage.removeItem(IMPERSONATION_BACKUP_KEY)
  localStorage.removeItem(IMPERSONATION_META_KEY)
  if (!raw) return false
  try {
    const backup = JSON.parse(raw) as { token?: string | null; user?: string | null }
    if (backup.token) localStorage.setItem(TOKEN_KEY, backup.token)
    if (backup.user) localStorage.setItem('user', backup.user)
    window.location.href = redirect
    return true
  } catch {
    return false
  }
}

// Em produção: VITE_API_URL aponta para o service API Railway
// Em dev: vite proxy redireciona /api para localhost:5001
export const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = getToken()
  const isFormData = body instanceof FormData
  const headers: Record<string, string> = {}
  if (!isFormData) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  const ctrl = new AbortController()
  const timeout = setTimeout(() => ctrl.abort(), 15000)

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method, headers,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal
    })
    const data = await res.json()
    if (!res.ok) {
      const msg = data.error || data.msg || `HTTP ${res.status}`
      if (res.status === 401) {
        if (!path.startsWith('/auth/')) {
          // WS6: token de visualização "ver como" expirou → restaura o
          // superadmin em vez de deslogar (flag p/ toast pós-reload)
          if (localStorage.getItem(IMPERSONATION_BACKUP_KEY)) {
            sessionStorage.setItem(IMPERSONATION_EXPIRED_FLAG, '1')
            if (restoreImpersonationBackup('/admin/tenants')) {
              throw new Error('Visualização encerrada (token expirou)')
            }
          }
          removeToken()
          window.location.href = '/login'
          throw new Error('Sessão expirada')
        }
        throw new Error(msg)
      }
      // Lazy-import to avoid circular deps
      import('../utils/errorTranslator').then(({ showErrorToast }) => {
        showErrorToast(res.status, path, msg)
      }).catch(() => {})
      throw new Error(msg)
    }
    return data
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      import('../utils/errorTranslator').then(({ showErrorToast }) => {
        showErrorToast(0, path, 'timeout')
      }).catch(() => {})
      throw new Error('Timeout na requisicao')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

export const api = {
  get:    <T>(path: string)              => request<T>('GET',    path),
  post:   <T>(path: string, b?: unknown) => request<T>('POST',   path, b),
  put:    <T>(path: string, b?: unknown) => request<T>('PUT',    path, b),
  patch:  <T>(path: string, b?: unknown) => request<T>('PATCH',  path, b),
  delete: <T>(path: string)              => request<T>('DELETE', path),

  /**
   * downloadBlob — authenticated file download (CSV/Excel/PDF).
   * Returns raw Blob; caller is responsible for triggering the browser download.
   * Use instead of raw fetch() for any endpoint that returns binary data.
   */
  downloadBlob: async (path: string): Promise<Blob> => {
    const token = getToken()
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    const ctrl = new AbortController()
    const timeout = setTimeout(() => ctrl.abort(), 30000)
    try {
      const res = await fetch(`${API_BASE}${path}`, { headers, signal: ctrl.signal })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.blob()
    } finally {
      clearTimeout(timeout)
    }
  },

  /**
   * fetchRaw — authenticated raw fetch that returns the native Response.
   * Use ONLY for endpoints that cannot return JSON — e.g. SSE/streaming responses.
   * Does NOT do JSON parsing or error toast; caller handles the response body.
   */
  fetchRaw: (path: string, init?: RequestInit): Promise<Response> => {
    const token = getToken()
    const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}
    return fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { ...authHeader, ...(init?.headers as Record<string, string> | undefined) },
    })
  },
}
