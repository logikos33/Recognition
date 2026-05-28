import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const container = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
})

export const label = style({
  fontFamily: vars.font.sans,
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textMuted,
  letterSpacing: '0.03em',
  userSelect: 'none',
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
})

export const switchRoot = style({
  width: '40px',
  height: '22px',
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.full,
  position: 'relative',
  cursor: 'pointer',
  transition: `background ${vars.animation.duration} ${vars.animation.easing}, border-color ${vars.animation.duration}`,
  selectors: {
    '&[data-state="checked"]': {
      background: vars.color.primary,
      borderColor: vars.color.primaryDark,
    },
  },
})

export const switchThumb = style({
  display: 'block',
  width: '16px',
  height: '16px',
  background: '#fff',
  borderRadius: vars.radius.full,
  position: 'absolute',
  top: '2px',
  left: '2px',
  transition: `transform ${vars.animation.duration} ${vars.animation.easing}`,
  selectors: {
    '[data-state="checked"] &': {
      transform: 'translateX(18px)',
    },
  },
})
