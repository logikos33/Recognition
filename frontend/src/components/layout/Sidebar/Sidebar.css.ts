import { style, keyframes } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const overlay = style({
  position: 'fixed',
  inset: 0,
  background: 'rgba(0, 0, 0, 0.6)',
  zIndex: 50,
  backdropFilter: 'blur(4px)',
  transition: `opacity ${vars.animation.duration} ${vars.animation.easing}`,
})

export const overlayHidden = style({
  opacity: 0,
  pointerEvents: 'none',
})

export const overlayVisible = style({
  opacity: 1,
})

export const sidebar = style({
  position: 'fixed',
  top: 0,
  left: 0,
  bottom: 0,
  width: '280px',
  background: vars.color.bgSurface,
  borderRight: `1px solid ${vars.color.borderDefault}`,
  zIndex: 51,
  display: 'flex',
  flexDirection: 'column',
  transition: `transform 300ms ${vars.animation.easing}`,
  boxShadow: vars.shadow.lg,
})

export const sidebarClosed = style({
  transform: 'translateX(-100%)',
})

export const sidebarOpen = style({
  transform: 'translateX(0)',
})

export const sidebarHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  height: '52px',
  flexShrink: 0,
})

export const sidebarTitle = style({
  fontSize: '15px',
  fontWeight: 700,
  color: vars.color.textPrimary,
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
})

export const closeBtn = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '32px',
  height: '32px',
  borderRadius: vars.radius.md,
  background: 'transparent',
  border: 'none',
  color: vars.color.textMuted,
  cursor: 'pointer',
  transition: `background ${vars.animation.duration}, color ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
  },
})

export const navSection = style({
  flex: 1,
  padding: `${vars.space.md} ${vars.space.sm}`,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
})

export const navItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.sm} ${vars.space.md}`,
  borderRadius: vars.radius.md,
  fontSize: '14px',
  fontWeight: 500,
  color: vars.color.textSecondary,
  textDecoration: 'none',
  transition: `background ${vars.animation.duration} ${vars.animation.easing}, color ${vars.animation.duration}`,
  cursor: 'pointer',
  border: 'none',
  background: 'transparent',
  width: '100%',
  textAlign: 'left',
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
  },
})

export const navItemActive = style([navItem, {
  background: vars.color.purple600,
  color: '#fff',
  fontWeight: 600,
  ':hover': {
    background: vars.color.purple500,
    color: '#fff',
  },
}])

export const navIcon = style({
  width: '20px',
  height: '20px',
  flexShrink: 0,
  opacity: 0.8,
})

export const divider = style({
  height: '1px',
  background: vars.color.borderSubtle,
  margin: `${vars.space.sm} ${vars.space.md}`,
})

export const footerSection = style({
  padding: `${vars.space.md} ${vars.space.sm}`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
})

export const versionBar = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${vars.space.sm} ${vars.space.md}`,
  fontSize: '11px',
  color: vars.color.textDim,
})

const pulse = keyframes({
  '0%, 100%': { opacity: 1 },
  '50%': { opacity: 0.4 },
})

export const statusDot = style({
  display: 'inline-block',
  width: '6px',
  height: '6px',
  borderRadius: '50%',
  background: vars.color.success,
  animation: `${pulse} 2s ease-in-out infinite`,
})
