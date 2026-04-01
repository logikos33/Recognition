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

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const ctrl = new AbortController()
  const timeout = setTimeout(() => ctrl.abort(), 15000)

  try {
    const res = await fetch(`/api${path}`, {
      method, headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
    return data
  } finally {
    clearTimeout(timeout)
  }
}

export const api = {
  get:    <T>(path: string)              => request<T>('GET',    path),
  post:   <T>(path: string, b?: unknown) => request<T>('POST',   path, b),
  put:    <T>(path: string, b?: unknown) => request<T>('PUT',    path, b),
  delete: <T>(path: string)              => request<T>('DELETE', path),
}
