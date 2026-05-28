import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const content = style({
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.sm,
  padding: `${vars.space.xs} ${vars.space.sm}`,
  fontFamily: vars.font.sans,
  fontSize: '12px',
  color: vars.color.textSecondary,
  boxShadow: vars.shadow.md,
  maxWidth: 280,
  zIndex: 100,
  animationDuration: '150ms',
  animationTimingFunction: vars.animation.easing,
})
