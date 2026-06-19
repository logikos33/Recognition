/**
 * ThemeProvider — injeta overrides de tenant como CSS vars no <head>.
 *
 * Sprint 6: chamada real à API (/v1/tenant/branding) com fallback
 * para mockData quando o usuário não está autenticado ou em dev sem backend.
 *
 * Funciona em runtime sem reload: troca de tenant troca o tema instantaneamente.
 */
import { useState, useEffect, type ReactNode } from 'react'
import { api } from '../services/api'
import { getMockTenantOverrides } from './tenant-theme/mockData'
import { resolveTheme } from './tenant-theme/resolver'
import type { TenantThemeOverrides } from './tenant-theme/types'

interface ThemeProviderProps {
  /** ID do tenant atual — vem do contexto de auth */
  tenantId?: string
  children: ReactNode
}

interface BrandingApiResponse {
  status: string
  data: Record<string, unknown>
}

export function ThemeProvider({ tenantId = 'logikos', children }: ThemeProviderProps) {
  const [overrides, setOverrides] = useState<TenantThemeOverrides>(
    () => getMockTenantOverrides(tenantId),
  )

  // Busca branding real da API; sem auth ou erro → mantém mock (tema padrão)
  useEffect(() => {
    let cancelled = false

    api
      .get<BrandingApiResponse>('/v1/tenant/branding')
      .then(res => {
        if (cancelled) return
        const d = res.data as Partial<TenantThemeOverrides>
        // Só aplica se a resposta tem pelo menos a chave 'brand'
        if (d && typeof d.brand === 'object') {
          setOverrides(d as TenantThemeOverrides)
        }
      })
      .catch(() => {
        // Sem auth, backend fora do ar ou coluna ainda não migrada → tema padrão silencioso
      })

    return () => {
      cancelled = true
    }
  }, [tenantId])

  // Injeta vars de override no :root sempre que overrides mudar
  useEffect(() => {
    const { cssVars } = resolveTheme(overrides)
    const styleId = 'recognition-tenant-theme'
    let styleEl = document.getElementById(styleId) as HTMLStyleElement | null

    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = styleId
      document.head.appendChild(styleEl)
    }

    const cssContent = Object.entries(cssVars)
      .map(([key, value]) => `  ${key}: ${value};`)
      .join('\n')

    styleEl.textContent = `:root {\n${cssContent}\n}`
  }, [overrides])

  return <>{children}</>
}
