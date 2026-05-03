/**
 * Recognition Dark — tema padrão da plataforma Recognition (Logikos).
 * Proposta B (Shop Floor): preto profundo, ciano elétrico, laranja-segurança.
 * Escolhido em Sprint 0 (Mai 2026).
 */
import { createTheme } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const recognitionDarkTheme = createTheme(vars, {
  color: {
    bgBase: '#0a0c10',
    bgSurface: '#111318',
    bgElevated: '#1e2330',
    bgCard: '#161a20',
    bgHover: '#1a1f27',

    textPrimary: '#f0f4f8',
    textSecondary: '#8ba3bc',
    textMuted: '#435060',
    textDim: '#2a3a4a',

    primary: '#06b6d4',
    primaryLight: '#22d3ee',
    primaryDark: '#0891b2',
    primaryAlpha: 'rgba(6, 182, 212, 0.1)',

    accent: '#ea580c',
    accentLight: '#f97316',
    accentDark: '#c2410c',
    accentAlpha: 'rgba(234, 88, 12, 0.12)',

    success: '#10b981',
    successMuted: 'rgba(16, 185, 129, 0.1)',
    warning: '#f59e0b',
    warningMuted: 'rgba(245, 158, 11, 0.1)',
    danger: '#ef4444',
    dangerMuted: 'rgba(239, 68, 68, 0.1)',

    borderSubtle: '#161c24',
    borderDefault: '#1e2730',
    borderStrong: '#2a3545',
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
    sans: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    mono: "'JetBrains Mono', 'Fira Code', monospace",
  },

  shadow: {
    sm: '0 2px 8px rgba(0, 0, 0, 0.5)',
    md: '0 4px 16px rgba(0, 0, 0, 0.6)',
    lg: '0 8px 40px rgba(0, 0, 0, 0.7)',
    glow: '0 0 0 3px rgba(6, 182, 212, 0.12)',
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
