import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const container = style({
  padding: 32,
  textAlign: 'center',
  color: vars.color.danger,
  background: vars.color.dangerMuted,
  borderRadius: vars.radius.lg,
  margin: 16,
})

export const heading = style({
  margin: '0 0 8px',
})

export const message = style({
  fontSize: 13,
  color: vars.color.textMuted,
})

export const retryButton = style({
  marginTop: 12,
  padding: '8px 16px',
  borderRadius: vars.radius.md,
  border: `1px solid ${vars.color.danger}`,
  background: vars.color.bgElevated,
  color: vars.color.danger,
  cursor: 'pointer',
  fontSize: 13,
})
