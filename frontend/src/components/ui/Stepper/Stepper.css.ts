import { style } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../../styles/theme.css'

export const stepper = recipe({
  base: {
    display: 'flex',
    gap: vars.space.sm,
  },
  variants: {
    orientation: {
      horizontal: { flexDirection: 'row', alignItems: 'center' },
      vertical: { flexDirection: 'column' },
    },
  },
  defaultVariants: { orientation: 'horizontal' },
})

export const stepItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  flex: 1,
})

export const stepConnector = style({
  flex: 1,
  height: 1,
  background: vars.color.borderDefault,
  selectors: {
    '[data-orientation="vertical"] &': {
      width: 1,
      height: 24,
      flex: 'none',
      margin: '0 0 0 11px',
    },
  },
})

export const stepCircle = recipe({
  base: {
    width: 24,
    height: 24,
    borderRadius: vars.radius.full,
    border: `2px solid`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '11px',
    fontWeight: 700,
    flexShrink: 0,
    fontFamily: vars.font.sans,
    transition: `all ${vars.animation.duration} ${vars.animation.easing}`,
  },
  variants: {
    state: {
      completed: {
        background: vars.color.primary,
        borderColor: vars.color.primary,
        color: vars.color.bgBase,
      },
      active: {
        background: 'transparent',
        borderColor: vars.color.primary,
        color: vars.color.primary,
      },
      pending: {
        background: 'transparent',
        borderColor: vars.color.borderDefault,
        color: vars.color.textMuted,
      },
    },
  },
  defaultVariants: { state: 'pending' },
})

export const stepLabel = style({
  fontFamily: vars.font.sans,
  fontSize: '12px',
  color: vars.color.textSecondary,
  whiteSpace: 'nowrap',
})
