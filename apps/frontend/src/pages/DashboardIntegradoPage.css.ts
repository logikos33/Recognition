import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  overflow: 'auto',
  padding: `${vars.space.lg} ${vars.space.xl}`,
  gap: vars.space.xl,
})

export const section = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
})

export const sectionHead = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.md,
  flexWrap: 'wrap',
})

export const sectionTitle = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  fontSize: 16,
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: 0,
})

export const connBadge = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  fontSize: 12,
  fontWeight: 600,
  padding: '4px 10px',
  borderRadius: vars.radius.full,
  border: `1px solid ${vars.color.borderSubtle}`,
  color: vars.color.textSecondary,
})

export const dot = style({
  width: 8,
  height: 8,
  borderRadius: vars.radius.full,
  background: vars.color.textMuted,
})

export const dotOn = style({ background: vars.color.success })
export const dotOff = style({ background: vars.color.danger })

export const chips = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: vars.space.sm,
})

export const chip = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  fontSize: 13,
  fontWeight: 600,
  padding: '6px 12px',
  borderRadius: vars.radius.full,
  border: `1px solid ${vars.color.borderStrong}`,
  background: vars.color.bgSurface,
  color: vars.color.textSecondary,
  cursor: 'pointer',
  userSelect: 'none',
})

export const chipActive = style({
  borderColor: vars.color.primary,
  background: vars.color.primaryAlpha,
  color: vars.color.textPrimary,
})

export const chipSwatch = style({
  width: 10,
  height: 10,
  borderRadius: 3,
  flexShrink: 0,
})

export const chartGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
  gap: vars.space.md,
})

export const card = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  padding: vars.space.lg,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: 12,
  background: vars.color.bgSurface,
})

export const cardHighlight = style({
  borderColor: vars.color.primary,
  boxShadow: vars.shadow.glow,
})

export const cardTitle = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  fontSize: 13,
  fontWeight: 600,
  color: vars.color.textSecondary,
})

export const cardBadge = style({
  fontSize: 11,
  fontWeight: 700,
  color: vars.color.primary,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
})

export const gaugeGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
  gap: vars.space.md,
})

export const gauge = style({
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  padding: vars.space.lg,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: 12,
  background: vars.color.bgSurface,
})

export const gaugeLabel = style({
  fontSize: 12,
  fontWeight: 600,
  color: vars.color.textMuted,
})

export const gaugeValue = style({
  fontSize: 26,
  fontWeight: 700,
  color: vars.color.textPrimary,
  fontVariantNumeric: 'tabular-nums',
})

export const gaugeUnit = style({
  fontSize: 13,
  fontWeight: 600,
  color: vars.color.textMuted,
  marginLeft: 4,
})

export const gaugeBar = style({
  position: 'relative',
  height: 6,
  borderRadius: vars.radius.full,
  background: vars.color.bgElevated,
  overflow: 'hidden',
})

export const gaugeFill = style({
  position: 'absolute',
  insetBlock: 0,
  left: 0,
  borderRadius: vars.radius.full,
  background: vars.color.primary,
})

export const fpsRow = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  fontSize: 13,
  padding: '6px 0',
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
})

export const fpsName = style({ color: vars.color.textSecondary })
export const fpsVal = style({
  color: vars.color.textPrimary,
  fontWeight: 600,
  fontVariantNumeric: 'tabular-nums',
})

export const select = style({
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: 6,
  color: vars.color.textPrimary,
  padding: '6px 10px',
  fontSize: 13,
  outline: 'none',
  cursor: 'pointer',
})
