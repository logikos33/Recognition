import { style } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../styles/theme.css'

export const container = style({
  background: 'rgba(30, 27, 75, 0.9)',
  border: `1px solid rgba(67, 56, 202, 0.6)`,
  borderRadius: vars.radius.lg,
  padding: vars.space.md,
  marginBottom: vars.space.md,
})

export const header = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  marginBottom: vars.space.sm,
})

export const sparkIcon = style({
  fontSize: '16px',
})

export const title = style({
  fontWeight: 700,
  color: vars.color.primaryLight,
  fontSize: '14px',
})

export const uncertaintyBadge = recipe({
  base: {
    fontSize: '12px',
    marginLeft: '4px',
  },
  variants: {
    level: {
      high: { color: vars.color.danger },
      medium: { color: vars.color.warning },
      low: { color: vars.color.success },
    },
  },
})

export const description = style({
  fontSize: '12px',
  color: vars.color.primary,
  margin: `0 0 14px`,
})

export const actions = style({
  display: 'flex',
  gap: vars.space.sm,
  flexWrap: 'wrap',
})
