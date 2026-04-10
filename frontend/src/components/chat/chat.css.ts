import { style, keyframes } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

const glowPulse = keyframes({
  '0%, 100%': { boxShadow: `0 0 12px rgba(139, 92, 246, 0.4)` },
  '50%': { boxShadow: `0 0 20px rgba(139, 92, 246, 0.7)` },
})

export const fab = style({
  position: 'fixed',
  bottom: '24px',
  right: '24px',
  width: '56px',
  height: '56px',
  borderRadius: '50%',
  background: vars.color.purple600,
  color: '#fff',
  border: 'none',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  animation: `${glowPulse} 3s ease-in-out infinite`,
  transition: 'transform 200ms, background 200ms',
  ':hover': {
    transform: 'scale(1.1)',
    background: vars.color.purple500,
  },
})

export const panelOverlay = style({
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.3)',
  zIndex: 1001,
})

export const chatPanel = style({
  position: 'fixed',
  top: 0,
  right: 0,
  bottom: 0,
  width: '400px',
  maxWidth: '100vw',
  background: vars.color.bgElevated,
  borderLeft: `1px solid ${vars.color.borderDefault}`,
  zIndex: 1002,
  display: 'flex',
  flexDirection: 'column',
})

export const chatHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
})

export const chatTitle = style({
  fontSize: '15px',
  fontWeight: 700,
  color: vars.color.textPrimary,
})

export const chatBody = style({
  flex: 1,
  overflowY: 'auto',
  padding: vars.space.md,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
})

export const msgSystem = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: 'rgba(139, 92, 246, 0.1)',
  borderRadius: vars.radius.md,
  borderLeft: `3px solid ${vars.color.purple500}`,
  fontSize: '13px',
  color: vars.color.textSecondary,
})

export const msgUser = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.purple600,
  borderRadius: vars.radius.md,
  fontSize: '13px',
  color: '#fff',
  alignSelf: 'flex-end',
  maxWidth: '80%',
})

export const msgBot = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.md,
  fontSize: '13px',
  color: vars.color.textSecondary,
  alignSelf: 'flex-start',
  maxWidth: '80%',
})

export const chatInputRow = style({
  display: 'flex',
  gap: vars.space.sm,
  padding: vars.space.md,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
})

export const chatInput = style({
  flex: 1,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: '13px',
  outline: 'none',
  ':focus': {
    borderColor: vars.color.purple500,
  },
})

export const chatSendBtn = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.purple600,
  color: '#fff',
  border: 'none',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  fontSize: '13px',
  fontWeight: 600,
  ':hover': {
    background: vars.color.purple500,
  },
  selectors: {
    '&:disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },
})
