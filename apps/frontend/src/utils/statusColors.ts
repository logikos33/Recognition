/**
 * Mapa compartilhado status → token de cor (task-063).
 * Usado por RegisteredToolsPanel, LiveVideoWithOperations e TrainingModeLayout
 * para manter o mesmo semáforo visual em toda a tela de Operação.
 */
import { vars } from '../styles/theme.css'

export const STATUS_COLORS: Record<string, string> = {
  active: vars.color.success,
  warning: vars.color.warning,
  error: vars.color.danger,
  inactive: vars.color.textMuted,
}

export function statusColor(status: string | undefined | null): string {
  return STATUS_COLORS[status ?? 'inactive'] ?? vars.color.textMuted
}
