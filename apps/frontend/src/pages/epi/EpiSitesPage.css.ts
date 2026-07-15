import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const page = style({
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  overflow: 'auto',
  padding: `${vars.space.lg} ${vars.space.xl}`,
  gap: vars.space.lg,
})

export const list = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
})

export const row = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.md,
  padding: `${vars.space.md} ${vars.space.lg}`,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: 10,
  background: vars.color.bgSurface,
})

export const rowInfo = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  minWidth: 0,
})

export const rowName = style({
  fontSize: 14,
  fontWeight: 600,
  color: vars.color.textPrimary,
})

export const rowMeta = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  fontSize: 12,
  color: vars.color.textMuted,
})

export const rowActions = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  flexShrink: 0,
})

export const modeSelect = style({
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderStrong}`,
  borderRadius: 6,
  color: vars.color.textPrimary,
  padding: '6px 10px',
  fontSize: 13,
  outline: 'none',
  cursor: 'pointer',
  minWidth: 180,
})
