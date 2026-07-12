/**
 * Defaults visuais da marca Recognition (recognition-dark.css.ts).
 * Fonte única para editor White-Label, previews e resets.
 */
import type { TenantSurfaceOverrides } from './types'

export const RECOGNITION_DEFAULT_PRIMARY = '#06b6d4'
export const RECOGNITION_DEFAULT_ACCENT = '#ea580c'

export const RECOGNITION_DEFAULT_SURFACES: Required<TenantSurfaceOverrides> = {
  bgBase: '#0a0c10',
  bgSurface: '#111318',
  bgElevated: '#1e2330',
  bgCard: '#161a20',
  textPrimary: '#f0f4f8',
  textSecondary: '#8ba3bc',
  border: '#1e2730',
}
