import { style, keyframes } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const card = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
  padding: `${vars.space.md} ${vars.space.lg}`,
  background: 'rgba(12, 12, 18, 0.8)',
  backdropFilter: 'blur(20px)',
  WebkitBackdropFilter: 'blur(20px)',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
  minWidth: '200px',
  flex: '1 1 0',
  transition: `border-color ${vars.animation.duration} ${vars.animation.easing}, box-shadow ${vars.animation.duration}`,
  ':hover': {
    borderColor: vars.color.borderStrong,
    boxShadow: '0 0 12px rgba(139, 92, 246, 0.1)',
  },
})

export const iconWrap = style({
  width: '40px',
  height: '40px',
  borderRadius: vars.radius.md,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
})

export const content = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  minWidth: 0,
})

export const label = style({
  fontSize: '11px',
  fontWeight: 600,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
})

export const valueRow = style({
  display: 'flex',
  alignItems: 'baseline',
  gap: vars.space.sm,
})

export const value = style({
  fontFamily: vars.font.mono,
  fontSize: '26px',
  fontWeight: 700,
  lineHeight: 1,
  color: vars.color.textPrimary,
})

export const subtext = style({
  fontSize: '11px',
  color: vars.color.textDim,
})

const pulseRed = keyframes({
  '0%, 100%': { opacity: 1 },
  '50%': { opacity: 0.4 },
})

export const alertPulse = style({
  animation: `${pulseRed} 1.5s ease-in-out infinite`,
})

export const trendUp = style({
  fontSize: '12px',
  fontWeight: 700,
  color: vars.color.success,
})

export const trendDown = style({
  fontSize: '12px',
  fontWeight: 700,
  color: vars.color.danger,
})
