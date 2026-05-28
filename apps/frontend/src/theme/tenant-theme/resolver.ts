/**
 * Resolve overrides do tenant sobre o tema base recognition-dark.
 * Sprint 1: injeta CSS vars via <style> tag no ThemeProvider.
 * Sprint 6: substituir getMockTenantOverrides por chamada à API.
 */
import type { TenantThemeOverrides, ResolvedTenantTheme } from './types'

/** Converte hex para rgba com alpha */
function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace('#', '')
  const r = parseInt(clean.slice(0, 2), 16)
  const g = parseInt(clean.slice(2, 4), 16)
  const b = parseInt(clean.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** Clarea uma cor hex em ~15% para gerar hover automático */
function lightenHex(hex: string): string {
  const clean = hex.replace('#', '')
  const r = Math.min(255, parseInt(clean.slice(0, 2), 16) + 30)
  const g = Math.min(255, parseInt(clean.slice(2, 4), 16) + 30)
  const b = Math.min(255, parseInt(clean.slice(4, 6), 16) + 30)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

/**
 * Gera o mapa de CSS vars a injetar com base nos overrides do tenant.
 * Somente sobrescreve cores que o tenant customizou; o resto vem do tema base.
 */
export function resolveTheme(overrides: TenantThemeOverrides): ResolvedTenantTheme {
  const cssVars: Record<string, string> = {}

  if (overrides.colors?.primary) {
    const p = overrides.colors.primary
    cssVars['--color-primary'] = p
    cssVars['--color-primary-light'] = overrides.colors.primaryHover ?? lightenHex(p)
    cssVars['--color-primary-alpha'] = hexToRgba(p, 0.1)
  }

  if (overrides.colors?.accent) {
    const a = overrides.colors.accent
    cssVars['--color-accent'] = a
    cssVars['--color-accent-alpha'] = hexToRgba(a, 0.12)
  }

  return { overrides, cssVars }
}
