import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: vars.space.md,
  padding: `${vars.space.xxl} ${vars.space.xl}`,
  textAlign: 'center',
})

export const icon = style({
  color: vars.color.textDim,
  opacity: 0.5,
})

export const title = style({
  fontFamily: vars.font.sans,
  fontSize: '15px',
  fontWeight: 600,
  color: vars.color.textSecondary,
  margin: 0,
})

export const description = style({
  fontFamily: vars.font.sans,
  fontSize: '13px',
  color: vars.color.textMuted,
  maxWidth: 320,
  margin: 0,
})
