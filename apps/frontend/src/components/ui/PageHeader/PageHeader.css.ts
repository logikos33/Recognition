/**
 * PageHeader.css.ts — cabeçalho canônico de página (WS1).
 * Substitui H1 hardcoded (#111827 e afins) por tokens do tema.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const header = style({
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: vars.space.md,
  marginBottom: vars.space.lg,
})

export const titleGroup = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
  minWidth: 0,
})

export const title = style({
  fontFamily: vars.font.sans,
  fontSize: '20px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  margin: 0,
  lineHeight: 1.25,
})

export const subtitle = style({
  fontFamily: vars.font.sans,
  fontSize: '13px',
  color: vars.color.textSecondary,
  margin: 0,
})

export const actions = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  flexShrink: 0,
})
