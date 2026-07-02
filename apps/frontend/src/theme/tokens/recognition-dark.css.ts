/**
 * Recognition Dark — tema padrão da plataforma Recognition (Logikos).
 * Proposta B (Shop Floor): preto profundo, ciano elétrico, laranja-segurança.
 * Escolhido em Sprint 0 (Mai 2026).
 *
 * WS1 (Jul 2026) — bridge white-label: cada token configurável por tenant
 * referencia uma CSS var plana com fallback no valor default da marca.
 * O ThemeProvider injeta essas vars em :root (via tenant-theme/resolver.ts),
 * retematizando TODO o UI kit sem rebuild. Valores compostos (rgba/shadow)
 * usam a var INTEIRA — nunca interpolação parcial.
 */
import { createTheme } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const recognitionDarkTheme = createTheme(vars, {
  color: {
    bgBase: 'var(--color-bg-base, #0a0c10)',
    bgSurface: 'var(--color-bg-surface, #111318)',
    bgElevated: 'var(--color-bg-elevated, #1e2330)',
    bgCard: 'var(--color-bg-card, #161a20)',
    bgHover: 'var(--color-bg-hover, #1a1f27)',

    textPrimary: 'var(--color-text-primary, #f0f4f8)',
    textSecondary: 'var(--color-text-secondary, #8ba3bc)',
    // WCAG AA: 4.76:1 on bgBase (was #435060 at 2.45:1)
    textMuted: 'var(--color-text-muted, #668096)',
    textDim: '#2a3a4a',

    primary: 'var(--color-primary, #06b6d4)',
    primaryLight: 'var(--color-primary-light, #22d3ee)',
    primaryDark: 'var(--color-primary-dark, #0891b2)',
    primaryAlpha: 'var(--color-primary-alpha, rgba(6, 182, 212, 0.1))',

    accent: 'var(--color-accent, #ea580c)',
    accentLight: 'var(--color-accent-light, #f97316)',
    accentDark: 'var(--color-accent-dark, #c2410c)',
    accentAlpha: 'var(--color-accent-alpha, rgba(234, 88, 12, 0.12))',

    success: '#10b981',
    successMuted: 'rgba(16, 185, 129, 0.1)',
    warning: '#f59e0b',
    warningMuted: 'rgba(245, 158, 11, 0.1)',
    danger: '#ef4444',
    dangerMuted: 'rgba(239, 68, 68, 0.1)',

    borderSubtle: 'var(--color-border-subtle, #161c24)',
    borderDefault: 'var(--color-border, #1e2730)',
    borderStrong: 'var(--color-border-strong, #2a3545)',

    overlay: 'rgba(0, 0, 0, 0.7)', // allow: overlay token canônico
    textOnPrimary: '#ffffff',
  },

  space: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },

  radius: {
    sm: '4px',
    md: '6px',
    lg: '10px',
    xl: '16px',
    full: '9999px',
  },

  font: {
    sans: "'Inter Variable', Inter, -apple-system, BlinkMacSystemFont, sans-serif",
    mono: "'JetBrains Mono', 'Fira Code', monospace",
  },

  shadow: {
    sm: '0 2px 8px rgba(0, 0, 0, 0.5)',
    md: '0 4px 16px rgba(0, 0, 0, 0.6)',
    lg: '0 8px 40px rgba(0, 0, 0, 0.7)',
    glow: 'var(--shadow-glow, 0 0 0 3px rgba(6, 182, 212, 0.12))',
    glowCyan: '0 0 12px rgba(6, 182, 212, 0.3)',
    glowDanger: '0 0 12px rgba(239, 68, 68, 0.3)',
  },

  animation: {
    enabled: '1',
    duration: '0.2s',
    durationSlow: '0.4s',
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
})
