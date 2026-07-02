/**
 * Panel.css.ts — superfície canônica de seção de página (WS1).
 * Variants: surface (painéis), card (blocos de conteúdo), elevated (destaques).
 * Panel NÃO substitui Card: Card é item de grid; Panel é seção com header.
 */
import { style } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../../styles/theme.css'

export const panel = recipe({
  base: {
    border: `1px solid ${vars.color.borderDefault}`,
    borderRadius: vars.radius.lg,
    overflow: 'hidden',
  },
  variants: {
    variant: {
      surface: { background: vars.color.bgSurface },
      card: { background: vars.color.bgCard },
      elevated: {
        background: vars.color.bgElevated,
        boxShadow: vars.shadow.sm,
      },
    },
    padding: {
      none: {},
      md: { padding: vars.space.md },
      lg: { padding: vars.space.lg },
    },
  },
  defaultVariants: { variant: 'surface', padding: 'none' },
})

export const panelHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.md,
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
})

export const panelTitle = style({
  fontFamily: vars.font.sans,
  fontSize: '15px',
  fontWeight: 600,
  color: vars.color.textPrimary,
  margin: 0,
})

export const panelSubtitle = style({
  fontFamily: vars.font.sans,
  fontSize: '12px',
  color: vars.color.textSecondary,
  margin: 0,
})

export const panelActions = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  flexShrink: 0,
})

export const panelBody = style({
  padding: vars.space.lg,
})
