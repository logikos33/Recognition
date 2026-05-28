/**
 * Auth centralizado.
 * LIÇÃO V1: estado inicializado do localStorage para sobreviver reload.
 * LIÇÃO V1: logout inline — sem depender de api.logout().
 */
import { useState, useCallback } from 'react'
import { api, setToken, removeToken, getToken } from '../services/api'

export interface User {
  id: string
  email: string
  name: string
  role: 'superadmin' | 'admin' | 'operator' | 'viewer'
  tenant_id?: string
  tenant_schema?: string
  modules?: string[]
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(() => {
    try { return JSON.parse(localStorage.getItem('user') || 'null') }
    catch { return null }
  })

  const isAuthenticated = !!(getToken() && user)

  // Helpers de autorização (não fazem request — apenas leem o estado em memória)
  const isSuperAdmin = user?.role === 'superadmin'
  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin'
  const modules = user?.modules ?? []
  const hasModule = (mod: string) => modules.includes(mod)

  const login = useCallback(async (email: string, password: string): Promise<User> => {
    const res = await api.post<any>('/auth/login', { email, password })
    const { token, user } = res.data  // ✅ correto: res.data contém {token, user}
    setToken(token)
    localStorage.setItem('user', JSON.stringify(user))
    setUser(user)
    // Reload para App.tsx ler do localStorage (hooks são instâncias separadas)
    window.location.href = '/'
    return user
  }, [])

  const logout = useCallback(() => {
    // LIÇÃO V1: inline — não depende de nenhuma função externa
    removeToken()
    setUser(null)
    window.location.href = '/'
  }, [])

  const register = useCallback(async (
    name: string, email: string, password: string
  ): Promise<User> => {
    const res = await api.post<any>('/auth/register', { name, email, password })
    const { token, user } = res.data  // ✅ correto
    setToken(token)
    localStorage.setItem('user', JSON.stringify(user))
    setUser(user)
    return user
  }, [])

  return { user, isAuthenticated, isSuperAdmin, isAdmin, modules, hasModule, login, logout, register }
}
