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

// Em produção: VITE_API_URL aponta para o service API Railway
// Em dev: vite proxy redireciona /api para localhost:5001
const API_BASE = import.meta.env.VITE_API_URL
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
}
