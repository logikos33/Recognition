import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const content = style({
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  padding: vars.space.md,
  boxShadow: vars.shadow.lg,
  zIndex: 50,
  minWidth: 200,
  animationDuration: '150ms',
  animationTimingFunction: vars.animation.easing,
})
