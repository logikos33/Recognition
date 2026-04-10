import { style, keyframes } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

const meshMove = keyframes({
  '0%': { backgroundPosition: '0% 50%' },
  '50%': { backgroundPosition: '100% 50%' },
  '100%': { backgroundPosition: '0% 50%' },
})

export const page = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: vars.space.xl,
  position: 'relative',
  overflow: 'hidden',
  '::before': {
    content: '""',
    position: 'absolute',
    inset: 0,
    background: `radial-gradient(ellipse at 20% 50%, rgba(139, 92, 246, 0.08) 0%, transparent 50%),
                 radial-gradient(ellipse at 80% 50%, rgba(6, 182, 212, 0.06) 0%, transparent 50%),
                 radial-gradient(ellipse at 50% 100%, rgba(139, 92, 246, 0.04) 0%, transparent 40%)`,
    backgroundSize: '200% 200%',
    animation: `${meshMove} 20s ease-in-out infinite`,
    pointerEvents: 'none',
  },
})

export const header = style({
  textAlign: 'center',
  marginBottom: vars.space.xxl,
  position: 'relative',
  zIndex: 1,
})

export const title = style({
  fontSize: '32px',
  fontWeight: 800,
  letterSpacing: '-0.02em',
  marginBottom: vars.space.sm,
  background: `linear-gradient(135deg, ${vars.color.textPrimary} 0%, ${vars.color.purple400} 100%)`,
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
})

export const subtitle = style({
  fontSize: '15px',
  color: vars.color.textSecondary,
  maxWidth: '480px',
})

export const cardsRow = style({
  display: 'flex',
  gap: vars.space.xl,
  position: 'relative',
  zIndex: 1,
  '@media': {
    '(max-width: 768px)': {
      flexDirection: 'column',
      alignItems: 'center',
    },
  },
})

export const card = style({
  width: '340px',
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.xl,
  padding: vars.space.xl,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
  cursor: 'pointer',
  transition: `transform ${vars.animation.duration} ${vars.animation.easing},
               box-shadow ${vars.animation.duration} ${vars.animation.easing},
               border-color ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': {
    transform: 'translateY(-4px)',
    boxShadow: vars.shadow.glow,
    borderColor: vars.color.borderGlow,
  },
})

export const cardDisabled = style([card, {
  opacity: 0.55,
  cursor: 'not-allowed',
  ':hover': {
    transform: 'none',
    boxShadow: 'none',
    borderColor: vars.color.borderDefault,
  },
}])

export const cardIconWrap = style({
  width: '56px',
  height: '56px',
  borderRadius: vars.radius.lg,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: `linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(6, 182, 212, 0.1))`,
  border: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
})

export const cardTitle = style({
  fontSize: '20px',
  fontWeight: 700,
  letterSpacing: '-0.01em',
  background: `linear-gradient(135deg, ${vars.color.textPrimary} 0%, ${vars.color.purple400} 100%)`,
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
})

export const cardDesc = style({
  fontSize: '14px',
  lineHeight: '1.6',
  color: vars.color.textSecondary,
})

const pulseGreen = keyframes({
  '0%, 100%': { boxShadow: '0 0 0 0 rgba(16, 185, 129, 0.4)' },
  '50%': { boxShadow: '0 0 0 4px rgba(16, 185, 129, 0)' },
})

export const badge = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '4px 12px',
  borderRadius: vars.radius.full,
  fontSize: '12px',
  fontWeight: 700,
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
  width: 'fit-content',
})

export const badgeActive = style([badge, {
  background: 'rgba(16, 185, 129, 0.15)',
  color: vars.color.success,
  border: `1px solid rgba(16, 185, 129, 0.3)`,
}])

export const badgeDot = style({
  width: '6px',
  height: '6px',
  borderRadius: '50%',
  background: vars.color.success,
  animation: `${pulseGreen} 2s ease-in-out infinite`,
})

export const badgeComingSoon = style([badge, {
  background: 'rgba(249, 115, 22, 0.15)',
  color: vars.color.warning,
  border: `1px solid rgba(249, 115, 22, 0.3)`,
}])

export const cardCta = style({
  marginTop: 'auto',
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.purple400,
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
})
