import { style } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../../styles/theme.css'

export const wrapper = style({
  width: '100%',
  height: '100%',
  background: vars.color.bgSurface,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  color: vars.color.textPrimary,
})

export const arrow = style({
  fontSize: 72,
  marginBottom: 24,
})

export const heading = style({
  fontSize: 36,
  fontWeight: 700,
  color: vars.color.primary,
  marginBottom: 12,
})

export const subheading = style({
  fontSize: 22,
  color: vars.color.primaryLight,
  marginBottom: 40,
})

export const pieceLabel = style({
  fontSize: 18,
  color: vars.color.primary,
  marginBottom: 40,
})

export const confirmBtn = recipe({
  base: {
    fontSize: 22,
    fontWeight: 700,
    padding: '20px 60px',
    color: vars.color.textPrimary,
    border: 'none',
    borderRadius: 12,
    minHeight: 70,
    transition: `background ${vars.animation.duration} ${vars.animation.easing}`,
  },
  variants: {
    loading: {
      true: {
        background: vars.color.bgElevated,
        cursor: 'not-allowed',
      },
      false: {
        background: vars.color.primary,
        cursor: 'pointer',
      },
    },
  },
  defaultVariants: { loading: false },
})
