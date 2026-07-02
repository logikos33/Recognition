/**
 * chartColors — cores tokenizadas para gráficos (Recharts/SVG) (WS1).
 * SVG aceita var(): stroke/fill/tick com estes valores retemam por tenant
 * junto com o restante do kit (bridge do recognition-dark).
 */
import { vars } from '../styles/theme.css'

export const chartColors = {
  primary: vars.color.primary,
  primaryLight: vars.color.primaryLight,
  accent: vars.color.accent,
  success: vars.color.success,
  warning: vars.color.warning,
  danger: vars.color.danger,
  grid: vars.color.borderDefault,
  axis: vars.color.textMuted,
  label: vars.color.textSecondary,
} as const

/** Paleta ordenada para séries múltiplas. */
export const chartSeries: readonly string[] = [
  chartColors.primary,
  chartColors.accent,
  chartColors.success,
  chartColors.warning,
  chartColors.danger,
  chartColors.primaryLight,
]
