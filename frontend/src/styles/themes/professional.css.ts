/**
 * Professional theme — dark static mode, no glows, no animations.
 * Same color palette as cyberpunk but more neutral borders/shadows.
 */
import { createTheme } from '@vanilla-extract/css'
import { vars } from '../theme.css'

export const professionalTheme = createTheme(vars, {
  color: {
    bgPrimary: '#0a0a0f',
    bgSurface: '#13131a',
    bgElevated: '#1a1a22',
    bgCard: '#20202a',
    bgHover: '#282832',

    textPrimary: '#f1f5f9',
    textSecondary: '#a1a1aa',
    textMuted: '#71717a',
    textDim: '#52525b',

    purple400: '#a78bfa',
    purple500: '#8b5cf6',
    purple600: '#7c3aed',
    cyan400: '#22d3ee',
    cyan500: '#06b6d4',

    success: '#10b981',
    successMuted: 'rgba(16, 185, 129, 0.12)',
    warning: '#f59e0b',
    danger: '#ef4444',
    dangerMuted: 'rgba(239, 68, 68, 0.12)',

    borderSubtle: 'rgba(255, 255, 255, 0.05)',
    borderDefault: 'rgba(255, 255, 255, 0.08)',
    borderStrong: 'rgba(255, 255, 255, 0.14)',
    borderGlow: 'rgba(255, 255, 255, 0.2)',
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
