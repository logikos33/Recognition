import { style } from '@vanilla-extract/css'

import { vars } from '../../styles/theme.css'

export const wrap = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.lg,
})

export const header = style({ display: 'flex', flexDirection: 'column', gap: vars.space.xs })
export const title = style({ fontSize: '1.1rem', fontWeight: 600, color: vars.color.textPrimary })
export const subtitle = style({ fontSize: '0.85rem', color: vars.color.textSecondary })

export const summary = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: vars.space.md,
  fontSize: '0.85rem',
  color: vars.color.textSecondary,
})
export const summaryStrong = style({ color: vars.color.textPrimary, fontWeight: 600 })

export const banner = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  borderRadius: vars.radius.md,
  fontSize: '0.85rem',
  border: `1px solid ${vars.color.borderDefault}`,
})
export const bannerWarn = style({
  background: vars.color.warningMuted,
  borderColor: vars.color.warning,
  color: vars.color.textPrimary,
})
export const bannerDanger = style({
  background: vars.color.dangerMuted,
  borderColor: vars.color.danger,
  color: vars.color.textPrimary,
})

export const legend = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: vars.space.md,
  alignItems: 'center',
  fontSize: '0.78rem',
  color: vars.color.textSecondary,
})
export const legendItem = style({ display: 'flex', alignItems: 'center', gap: vars.space.xs })
export const swatch = style({
  width: 14,
  height: 14,
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderSubtle}`,
})

// --- matriz ---
export const scroll = style({
  overflowX: 'auto',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
})
export const table = style({
  borderCollapse: 'separate',
  borderSpacing: 0,
  fontFamily: vars.font.mono,
  fontSize: '0.8rem',
})
export const cornerTh = style({
  position: 'sticky',
  left: 0,
  zIndex: 3,
  background: vars.color.bgSurface,
  textAlign: 'left',
  padding: vars.space.sm,
  minWidth: 220,
  borderBottom: `1px solid ${vars.color.borderDefault}`,
})
export const camTh = style({
  padding: vars.space.xs,
  minWidth: 40,
  maxWidth: 52,
  textAlign: 'center',
  verticalAlign: 'bottom',
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  borderLeft: `1px solid ${vars.color.borderSubtle}`,
  cursor: 'pointer',
  color: vars.color.textSecondary,
})
export const camThInactive = style({ opacity: 0.45 })
export const camCode = style({ fontWeight: 600, color: vars.color.textPrimary })
export const camMeta = style({ fontSize: '0.62rem', color: vars.color.textMuted })

export const classTd = style({
  position: 'sticky',
  left: 0,
  zIndex: 2,
  background: vars.color.bgCard,
  padding: vars.space.sm,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  borderRight: `1px solid ${vars.color.borderDefault}`,
  minWidth: 220,
})
export const classNameRow = style({ display: 'flex', alignItems: 'center', gap: vars.space.xs })
export const dot = style({ width: 10, height: 10, borderRadius: vars.radius.full, flexShrink: 0 })
export const classLabel = style({ fontWeight: 600, color: vars.color.textPrimary, fontFamily: vars.font.sans })
export const chips = style({ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' })
export const chip = style({
  fontSize: '0.68rem',
  padding: '1px 6px',
  borderRadius: vars.radius.full,
  fontFamily: vars.font.sans,
  border: `1px solid ${vars.color.borderSubtle}`,
  color: vars.color.textSecondary,
})
export const chipOk = style({ background: vars.color.successMuted, color: vars.color.success, borderColor: vars.color.success })
export const chipWarn = style({ background: vars.color.warningMuted, color: vars.color.warning, borderColor: vars.color.warning })
export const chipBad = style({ background: vars.color.dangerMuted, color: vars.color.danger, borderColor: vars.color.danger })

export const cell = style({
  textAlign: 'center',
  padding: vars.space.xs,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  borderLeft: `1px solid ${vars.color.borderSubtle}`,
  cursor: 'pointer',
  color: vars.color.textPrimary,
})
export const cellZero = style({ background: vars.color.dangerMuted, color: vars.color.danger })
export const cellLow = style({ background: vars.color.warningMuted })
export const cellMid = style({ background: vars.color.successMuted })
export const cellHigh = style({ background: vars.color.success, color: vars.color.textOnPrimary })
export const stragglerRow = style({ opacity: 0.6 })

// --- painéis de ação ---
export const panels = style({ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: vars.space.lg })
export const panel = style({
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  padding: vars.space.md,
  background: vars.color.bgCard,
})
export const panelTitle = style({ fontSize: '0.95rem', fontWeight: 600, marginBottom: vars.space.sm, color: vars.color.textPrimary })
export const gapRow = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.sm,
  padding: `${vars.space.xs} 0`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  cursor: 'pointer',
})
export const gapLeft = style({ display: 'flex', flexDirection: 'column' })
export const gapClass = style({ fontWeight: 600, color: vars.color.textPrimary })
export const gapReason = style({ fontSize: '0.72rem', color: vars.color.textMuted })
export const gapCta = style({ fontSize: '0.78rem', color: vars.color.primary, whiteSpace: 'nowrap' })

export const state = style({ padding: vars.space.xl, textAlign: 'center', color: vars.color.textSecondary })
