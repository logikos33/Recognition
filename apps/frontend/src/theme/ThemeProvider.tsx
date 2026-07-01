/**
 * ThemeProvider — injeta overrides de tenant como CSS vars no <head>.
 * Sprint 6: carrega branding real da API (task-048).
 *
 * Fluxo:
 *  1. Monta com tenantId do JWT
 *  2. Faz GET /api/v1/tenant/branding?tenant_id=<id>
 *  3. Converte resposta para TenantThemeOverrides e aplica CSS vars
 *  4. Fallback silencioso para tema Recognition padrão em caso de erro
 */
import { useEffect, type ReactNode } from 'react'
import { resolveTheme } from './tenant-theme/resolver'
import type { TenantThemeOverrides } from './tenant-theme/types'
import { getToken } from '../services/api'

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

/** Branding padrão Recognition — aplicado quando o tenant não tem overrides. */
const DEFAULT_OVERRIDES: TenantThemeOverrides = {
  brand: { productName: 'Recognition' },
  colors: {},
}

/** Converte a resposta da API (snake_case) para TenantThemeOverrides. */
function apiToOverrides(branding: Record<string, string | null>): TenantThemeOverrides {
  return {
    brand: {
      productName: branding.product_name ?? 'Recognition',
      logoUrl:     branding.logo_url    ?? undefined,
      logoMonoUrl: undefined,
    },
    colors: {
      primary:  branding.color_primary   ?? undefined,
      accent:   branding.color_secondary ?? undefined,
    },
  }
}

/** Aplica favicon dinamicamente se a URL mudar. */
function applyFavicon(faviconUrl: string | null | undefined) {
  if (!faviconUrl) return
  let link = document.querySelector<HTMLLinkElement>('link[rel~="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = faviconUrl
}

interface ThemeProviderProps {
  /** ID do tenant atual — vem do contexto de auth (user.tenant_id). */
  tenantId?: string
  children: ReactNode
}

export function ThemeProvider({ tenantId, children }: ThemeProviderProps) {
  useEffect(() => {
    let cancelled = false

    async function loadBranding() {
      let overrides = DEFAULT_OVERRIDES
      let faviconUrl: string | null = null

      try {
        const qs = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ''
        const token = getToken()
        const headers: Record<string, string> = {}
        if (token) headers['Authorization'] = `Bearer ${token}`

        const res = await fetch(`${API_BASE}/v1/tenant/branding${qs}`, {
          headers,
          signal: AbortSignal.timeout(5000),
        })

        if (res.ok) {
          const payload = await res.json()
          const branding = payload?.data?.branding
          if (branding && !payload?.data?.is_default) {
            overrides = apiToOverrides(branding)
            faviconUrl = branding.favicon_url ?? null
          }
        }
      } catch {
        // Silently fall back to default theme
      }

      if (cancelled) return

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

      // Update document title with product name
      const productName = overrides.brand.productName ?? 'Recognition'
      if (document.title === 'Recognition' || document.title.endsWith('| Recognition')) {
        document.title = productName
      }

      applyFavicon(faviconUrl)
    }

    loadBranding()

    return () => {
      cancelled = true
    }
  }, [tenantId])

  return <>{children}</>
}
