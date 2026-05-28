/**
 * Legacy: Cyberpunk theme — dark gamer mode, purple/cyan, animations enabled.
 * Mantido para compatibilidade. Tema padrão migrou para recognition-dark.
 * Tokens renomeados em Sprint 1 (Recognition rebrand, Mai 2026):
 *   purple500 → primary, cyan400 → accent, bgPrimary → bgBase.
 */
import { createTheme } from '@vanilla-extract/css'
import { vars } from '../theme.css'

export const cyberpunkTheme = createTheme(vars, {
  color: {
    bgBase: '#030305',
    bgSurface: '#0c0c12',
    bgElevated: '#121218',
    bgCard: '#18181f',
    bgHover: '#1e1e28',

    textPrimary: '#f1f5f9',
    textSecondary: '#94a3b8',
    textMuted: '#64748b',
    textDim: '#475569',

    primary: '#8b5cf6',
    primaryLight: '#a78bfa',
    primaryDark: '#7c3aed',
    primaryAlpha: 'rgba(139, 92, 246, 0.12)',

    accent: '#22d3ee',
    accentLight: '#67e8f9',
    accentDark: '#06b6d4',
    accentAlpha: 'rgba(34, 211, 238, 0.1)',

    success: '#10b981',
    successMuted: 'rgba(16, 185, 129, 0.15)',
    warning: '#f59e0b',
    warningMuted: 'rgba(245, 158, 11, 0.12)',
    danger: '#ef4444',
    dangerMuted: 'rgba(239, 68, 68, 0.15)',

    borderSubtle: 'rgba(139, 92, 246, 0.20)',
    borderDefault: 'rgba(139, 92, 246, 0.32)',
    borderStrong: 'rgba(139, 92, 246, 0.52)',
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
    sm: '0 2px 8px rgba(0, 0, 0, 0.4)',
    md: '0 4px 16px rgba(0, 0, 0, 0.5)',
    lg: '0 8px 32px rgba(0, 0, 0, 0.6)',
    glow: '0 0 20px rgba(139, 92, 246, 0.4), 0 0 40px rgba(139, 92, 246, 0.15)',
    glowCyan: '0 0 20px rgba(34, 211, 238, 0.4), 0 0 40px rgba(34, 211, 238, 0.15)',
    glowDanger: '0 0 20px rgba(239, 68, 68, 0.4)',
  },

  animation: {
    enabled: '1',
    duration: '0.25s',
    durationSlow: '0.5s',
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
})
