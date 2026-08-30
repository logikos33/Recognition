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
  // WS7 fix (P3): union incluía só 4 roles — 'analyst' e 'trainer' existem
  // no backend desde a migration 029
  role: 'superadmin' | 'admin' | 'operator' | 'analyst' | 'trainer' | 'viewer'
  tenant_id?: string
  tenant_schema?: string
  modules?: string[]
  /** WS7 — permissões efetivas ('dominio:acao') retornadas no login. */
  permissions?: string[]
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

  /** WS7 — gating de UI por permissão efetiva ('dominio:acao'). */
  const can = (permission: string): boolean => {
    if (!user) return false
    if (user.role === 'superadmin') return true
    return user.permissions?.includes(permission) ?? false
  }

  const login = useCallback(async (
    email: string, password: string, redirectTo = '/'
  ): Promise<User> => {
    const res = await api.post<any>('/auth/login', { email, password })
    const { token, user } = res.data  // ✅ correto: res.data contém {token, user}
    setToken(token)
    localStorage.setItem('user', JSON.stringify(user))
    setUser(user)
    // Reload para App.tsx ler do localStorage (hooks são instâncias separadas).
    // ⚠️ `redirectTo` SÓ aceita literais internos dos call sites — nunca ligue
    // a query param (`params.get('next')`): vira open-redirect (achado do cético).
    // `redirectTo` default '/' preserva o Login antigo; a Entrar nova (F5 SR2)
    // manda rotaNova('/') para cair no front novo pós-login.
    window.location.href = redirectTo
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

  return { user, isAuthenticated, isSuperAdmin, isAdmin, modules, hasModule, can, login, logout, register }
}
