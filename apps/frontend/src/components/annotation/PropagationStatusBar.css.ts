/**
 * PropagationStatusBar styles — barra horizontal que OCUPA espaço no
 * layout (filho normal do flex column, nunca position:absolute/fixed).
 * Mesmos tokens de AnnotationStudio.css.ts (white-label).
 */
import { keyframes, style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

const spin = keyframes({
  from: { transform: 'rotate(0deg)' },
  to: { transform: 'rotate(360deg)' },
})

export const spinIcon = style({
  animation: `${spin} 1.1s linear infinite`,
  flexShrink: 0,
})

export const bar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  minHeight: '32px',
  padding: `4px ${vars.space.md}`,
  fontSize: '12px',
  color: vars.color.textSecondary,
  background: vars.color.bgSurface,
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  flexShrink: 0,
})

export const barDanger = style({
  background: vars.color.dangerMuted,
  color: vars.color.danger,
  borderBottomColor: vars.color.danger,
})

export const barSuccess = style({
  background: vars.color.successMuted,
  color: vars.color.success,
  borderBottomColor: vars.color.success,
})

export const label = style({
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  fontWeight: 600,
  flexShrink: 1,
})

export const elapsed = style({
  fontFamily: vars.font.mono,
  fontSize: '11px',
  opacity: 0.85,
  whiteSpace: 'nowrap',
  flexShrink: 0,
})

export const track = style({
  position: 'relative',
  flex: '0 1 220px',
  minWidth: '80px',
  height: '4px',
  borderRadius: vars.radius.full,
  background: vars.color.bgCard,
  overflow: 'hidden',
})

export const fill = style({
  position: 'absolute',
  top: 0,
  left: 0,
  bottom: 0,
  borderRadius: vars.radius.full,
  background: vars.color.primary,
  transition: 'width 0.4s ease',
})

const indeterminateAnim = keyframes({
  '0%': { left: '-40%', width: '40%' },
  '50%': { left: '30%', width: '55%' },
  '100%': { left: '100%', width: '40%' },
})

export const fillIndeterminate = style({
  position: 'absolute',
  top: 0,
  bottom: 0,
  width: '40%',
  borderRadius: vars.radius.full,
  background: vars.color.primary,
  animation: `${indeterminateAnim} 1.4s ease-in-out infinite`,
})

export const spacer = style({ flex: 1, minWidth: '4px' })

export const linkButton = style({
  fontSize: '12px',
  fontWeight: 700,
  color: 'inherit',
  background: 'transparent',
  border: 'none',
  textDecoration: 'underline',
  cursor: 'pointer',
  padding: 0,
  flexShrink: 0,
  selectors: {
    '&:hover': { opacity: 0.8 },
  },
})

export const detailsToggle = style({
  fontSize: '11px',
  color: 'inherit',
  background: 'transparent',
  border: 'none',
  textDecoration: 'underline',
  cursor: 'pointer',
  padding: 0,
  flexShrink: 0,
})

export const detailsText = style({
  fontSize: '11px',
  fontFamily: vars.font.mono,
  opacity: 0.85,
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  maxWidth: '360px',
})

export const closeButton = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '20px',
  height: '20px',
  color: 'inherit',
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  opacity: 0.75,
  flexShrink: 0,
  selectors: {
    '&:hover': { opacity: 1, background: 'rgba(0,0,0,0.08)' },
  },
})
