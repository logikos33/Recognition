/**
 * ThemeProvider — injeta overrides de tenant como CSS vars no <head>.
 * Sprint 1: usa mockData; Sprint 6 substituirá por chamada à API real.
 *
 * Funciona em runtime sem reload: troca de tenant troca o tema instantaneamente.
 */
import { useEffect, type ReactNode } from 'react'
import { getMockTenantOverrides } from './tenant-theme/mockData'
import { resolveTheme } from './tenant-theme/resolver'

interface ThemeProviderProps {
  /** ID do tenant atual — vem do contexto de auth */
  tenantId?: string
  children: ReactNode
}

export function ThemeProvider({ tenantId = 'logikos', children }: ThemeProviderProps) {
  useEffect(() => {
    const overrides = getMockTenantOverrides(tenantId)
    const { cssVars } = resolveTheme(overrides)

    // Injeta vars de override no :root — sobrescreve valores do tema base
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

    return () => {
      // Limpa ao desmontar (troca de tenant)
      if (styleEl) styleEl.textContent = ''
    }
  }, [tenantId])

  return <>{children}</>
}
