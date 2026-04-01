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
  role: 'admin' | 'operator'
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(() => {
    try { return JSON.parse(localStorage.getItem('user') || 'null') }
    catch { return null }
  })

  const isAuthenticated = !!(getToken() && user)

  const login = useCallback(async (email: string, password: string): Promise<User> => {
    const res = await api.post<any>('/auth/login', { email, password })
    const { token, data } = res
    setToken(token)
    localStorage.setItem('user', JSON.stringify(data.user))
    setUser(data.user)
    return data.user
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
    const { token, data } = res
    setToken(token)
    localStorage.setItem('user', JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }, [])

  return { user, isAuthenticated, login, logout, register }
}
