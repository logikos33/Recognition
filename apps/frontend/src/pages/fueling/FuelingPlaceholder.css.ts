import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const wrapper = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '60vh',
  textAlign: 'center',
  padding: 32,
})

export const iconCircle = style({
  fontSize: 64,
  width: 120,
  height: 120,
  borderRadius: vars.radius.full,
  background: vars.color.bgSurface,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: 24,
})

export const title = style({
  fontSize: 24,
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: '0 0 8px',
})

export const description = style({
  fontSize: 14,
  color: vars.color.textMuted,
  maxWidth: 420,
  lineHeight: 1.6,
  margin: '0 0 24px',
})

export const badge = style({
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: 13,
  color: vars.color.textSecondary,
  background: vars.color.bgSurface,
  padding: '8px 16px',
  borderRadius: vars.radius.full,
})
