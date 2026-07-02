/**
 * Legacy: Professional theme — dark static mode, no glows, no animations.
 * Mantido para compatibilidade. Tema padrão migrou para recognition-dark.
 * Tokens renomeados em Sprint 1 (Recognition rebrand, Mai 2026):
 *   purple500 → primary, cyan400 → accent, bgPrimary → bgBase.
 */
import { createTheme } from '@vanilla-extract/css'
import { vars } from '../theme.css'

export const professionalTheme = createTheme(vars, {
  color: {
    bgBase: '#0a0a0f',
    bgSurface: '#13131a',
    bgElevated: '#1a1a22',
    bgCard: '#20202a',
    bgHover: '#282832',

    textPrimary: '#f1f5f9',
    textSecondary: '#a1a1aa',
    textMuted: '#71717a',
    textDim: '#52525b',

    primary: '#8b5cf6',
    primaryLight: '#a78bfa',
    primaryDark: '#7c3aed',
    primaryAlpha: 'rgba(139, 92, 246, 0.1)',

    accent: '#22d3ee',
    accentLight: '#67e8f9',
    accentDark: '#06b6d4',
    accentAlpha: 'rgba(34, 211, 238, 0.08)',

    success: '#10b981',
    successMuted: 'rgba(16, 185, 129, 0.12)',
    warning: '#f59e0b',
    warningMuted: 'rgba(245, 158, 11, 0.1)',
    danger: '#ef4444',
    dangerMuted: 'rgba(239, 68, 68, 0.12)',

    borderSubtle: 'rgba(255, 255, 255, 0.05)',
    borderDefault: 'rgba(255, 255, 255, 0.08)',
    borderStrong: 'rgba(255, 255, 255, 0.14)',

    overlay: 'rgba(0, 0, 0, 0.7)',
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
    sm: '6px',
    md: '10px',
    lg: '16px',
    xl: '20px',
    full: '9999px',
  },

  font: {
    sans: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    mono: "'JetBrains Mono', 'Fira Code', monospace",
  },

  shadow: {
    sm: '0 2px 8px rgba(0, 0, 0, 0.3)',
    md: '0 4px 16px rgba(0, 0, 0, 0.4)',
    lg: '0 8px 32px rgba(0, 0, 0, 0.5)',
    glow: 'none',
    glowCyan: 'none',
    glowDanger: 'none',
  },

  animation: {
    enabled: '0',
    duration: '0s',
    durationSlow: '0s',
    easing: 'linear',
  },
})
