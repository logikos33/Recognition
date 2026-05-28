import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const footer = style({
  height: 32,
  background: vars.color.bgSurface,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  alignItems: 'center',
  padding: `0 ${vars.space.lg}`,
  gap: vars.space.lg,
  flexShrink: 0,
  zIndex: 10,
})

export const item = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
  fontSize: 11,
  color: vars.color.textDim,
  fontFamily: 'JetBrains Mono, Consolas, monospace',
})

const dot = style({
  width: 7,
  height: 7,
  borderRadius: vars.radius.full,
  display: 'inline-block',
  flexShrink: 0,
})

export const dotOk = style([dot, { background: vars.color.success }])
export const dotErr = style([dot, { background: vars.color.danger }])
export const dotNeutral = style([dot, { background: vars.color.textDim }])

export const separator = style({
  width: 1,
  height: 16,
  background: vars.color.borderSubtle,
  flexShrink: 0,
})
