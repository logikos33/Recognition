/**
 * AppDrawer.css.ts — estilos do contêiner gaveta lateral (deliverable l).
 * Abre pelo lado direito sobre o contexto atual.
 */
import { style, keyframes } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../../styles/theme.css'

const overlayIn = keyframes({
  from: { opacity: 0 },
  to: { opacity: 1 },
})

const slideIn = keyframes({
  from: { transform: 'translateX(100%)' },
  to: { transform: 'translateX(0)' },
})

export const overlay = style({
  position: 'fixed',
  inset: 0,
  background: vars.color.overlay,
  zIndex: 200,
  backdropFilter: 'blur(3px)',
  animationName: overlayIn,
  animationDuration: vars.animation.duration,
  animationTimingFunction: vars.animation.easing,
})

export const drawer = recipe({
  base: {
    position: 'fixed',
    top: 0,
    right: 0,
    bottom: 0,
    display: 'flex',
    flexDirection: 'column',
    background: vars.color.bgElevated,
    borderLeft: `1px solid ${vars.color.borderDefault}`,
    boxShadow: vars.shadow.lg,
    zIndex: 201,
    overflow: 'hidden',
    animationName: slideIn,
    animationDuration: vars.animation.duration,
    animationTimingFunction: vars.animation.easing,
  },
  variants: {
    size: {
      sm: { width: 'min(360px, 100vw)' },
      md: { width: 'min(480px, 100vw)' },
      lg: { width: 'min(660px, 100vw)' },
      xl: { width: 'min(860px, 100vw)' },
    },
  },
  defaultVariants: { size: 'md' },
})

export const drawerHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
  gap: vars.space.sm,
})

export const drawerTitle = style({
  fontFamily: vars.font.sans,
  fontWeight: 700,
  fontSize: '15px',
  color: vars.color.textPrimary,
  margin: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  flex: 1,
})

export const closeBtn = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '30px',
  height: '30px',
  background: 'transparent',
  border: 'none',
  color: vars.color.textMuted,
  cursor: 'pointer',
  borderRadius: vars.radius.sm,
  flexShrink: 0,
  transition: `background ${vars.animation.duration}, color ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
  },
})

export const drawerBody = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  minHeight: 0,
})
