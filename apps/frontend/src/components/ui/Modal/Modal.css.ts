import { style, keyframes } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

const overlayShow = keyframes({
  from: { opacity: 0 },
  to: { opacity: 1 },
})

const contentShow = keyframes({
  from: { opacity: 0, transform: 'translate(-50%, -48%) scale(0.96)' },
  to: { opacity: 1, transform: 'translate(-50%, -50%) scale(1)' },
})

export const overlay = style({
  background: vars.color.overlay,
  position: 'fixed',
  inset: 0,
  zIndex: 50,
  backdropFilter: 'blur(4px)',
  animationName: overlayShow,
  animationDuration: vars.animation.duration,
  animationTimingFunction: vars.animation.easing,
})

export const content = style({
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.xl,
  boxShadow: vars.shadow.lg,
  position: 'fixed',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  width: '90vw',
  maxWidth: '520px',
  maxHeight: '90vh',
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column',
  zIndex: 51,
  animationName: contentShow,
  animationDuration: vars.animation.duration,
  animationTimingFunction: vars.animation.easing,
})

export const header = style({
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexShrink: 0,
})

export const title = style({
  fontFamily: vars.font.sans,
  fontWeight: 700,
  fontSize: '16px',
  color: vars.color.textPrimary,
  margin: 0,
})

export const closeButton = style({
  background: 'none',
  border: 'none',
  color: vars.color.textMuted,
  cursor: 'pointer',
  padding: vars.space.xs,
  borderRadius: vars.radius.sm,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: `color ${vars.animation.duration}`,
  ':hover': {
    color: vars.color.textPrimary,
    background: vars.color.bgHover,
  },
})

export const body = style({
  padding: vars.space.lg,
  overflowY: 'auto',
  flex: 1,
})

export const footer = style({
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexShrink: 0,
  background: vars.color.bgSurface,
})
