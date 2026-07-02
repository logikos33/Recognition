/**
 * Resolve overrides do tenant sobre o tema base recognition-dark.
 * Injeta CSS vars planas via <style> tag no ThemeProvider — o tema
 * recognition-dark.css.ts referencia cada var com fallback no default
 * da marca, então SOMENTE as chaves customizadas pelo tenant sobrescrevem.
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

/** Clarea uma cor hex (delta por canal) — hover automático */
export function lightenHex(hex: string, amount = 30): string {
  const clean = hex.replace('#', '')
  const r = Math.min(255, parseInt(clean.slice(0, 2), 16) + amount)
  const g = Math.min(255, parseInt(clean.slice(2, 4), 16) + amount)
  const b = Math.min(255, parseInt(clean.slice(4, 6), 16) + amount)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

/** Escurece uma cor hex (delta por canal) — active/pressed automático */
export function darkenHex(hex: string, amount = 30): string {
  const clean = hex.replace('#', '')
  const r = Math.max(0, parseInt(clean.slice(0, 2), 16) - amount)
  const g = Math.max(0, parseInt(clean.slice(2, 4), 16) - amount)
  const b = Math.max(0, parseInt(clean.slice(4, 6), 16) - amount)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

/**
 * Gera o mapa de CSS vars a injetar com base nos overrides do tenant.
 * Somente sobrescreve cores que o tenant customizou; o resto vem do tema base
 * (fallback do var() no recognition-dark.css.ts).
 */
export function resolveTheme(overrides: TenantThemeOverrides): ResolvedTenantTheme {
  const cssVars: Record<string, string> = {}

  if (overrides.colors?.primary) {
    const p = overrides.colors.primary
    cssVars['--color-primary'] = p
    cssVars['--color-primary-light'] = overrides.colors.primaryHover ?? lightenHex(p)
    cssVars['--color-primary-dark'] = darkenHex(p)
    cssVars['--color-primary-alpha'] = hexToRgba(p, 0.1)
    cssVars['--shadow-glow'] = `0 0 0 3px ${hexToRgba(p, 0.12)}`
  }

  if (overrides.colors?.accent) {
    const a = overrides.colors.accent
    cssVars['--color-accent'] = a
    cssVars['--color-accent-light'] = lightenHex(a)
    cssVars['--color-accent-dark'] = darkenHex(a)
    cssVars['--color-accent-alpha'] = hexToRgba(a, 0.12)
  }

  const s = overrides.surfaces
  if (s?.bgBase) cssVars['--color-bg-base'] = s.bgBase
  if (s?.bgSurface) {
    cssVars['--color-bg-surface'] = s.bgSurface
    // hover derivado da superfície (leve clareada)
    cssVars['--color-bg-hover'] = lightenHex(s.bgSurface, 10)
  }
  if (s?.bgElevated) cssVars['--color-bg-elevated'] = s.bgElevated
  if (s?.bgCard) cssVars['--color-bg-card'] = s.bgCard
  if (s?.textPrimary) cssVars['--color-text-primary'] = s.textPrimary
  if (s?.textSecondary) {
    cssVars['--color-text-secondary'] = s.textSecondary
    // muted derivado do secundário (escurecido)
    cssVars['--color-text-muted'] = darkenHex(s.textSecondary, 24)
  }
  if (s?.border) {
    cssVars['--color-border'] = s.border
    cssVars['--color-border-subtle'] = darkenHex(s.border, 10)
    cssVars['--color-border-strong'] = lightenHex(s.border, 18)
  }

  return { overrides, cssVars }
}
