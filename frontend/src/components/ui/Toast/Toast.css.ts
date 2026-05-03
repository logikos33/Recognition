import { style, keyframes } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../../styles/theme.css'

const slideIn = keyframes({
  from: { transform: 'translateX(calc(100% + 16px))', opacity: 0 },
  to: { transform: 'translateX(0)', opacity: 1 },
})

const fadeOut = keyframes({
  from: { opacity: 1 },
  to: { opacity: 0 },
})

export const viewport = style({
  position: 'fixed',
  top: 16,
  right: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  zIndex: 9999,
  width: 340,
  pointerEvents: 'none',
})

export const toast = recipe({
  base: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: vars.space.sm,
    padding: `${vars.space.sm} ${vars.space.md}`,
    borderRadius: vars.radius.md,
    border: '1px solid',
    boxShadow: vars.shadow.lg,
    fontFamily: vars.font.sans,
    fontSize: '13px',
    pointerEvents: 'all',
    animation: `${slideIn} 0.2s ease`,
    selectors: {
      '&[data-state="closed"]': { animation: `${fadeOut} 0.15s ease` },
    },
  },
  variants: {
    variant: {
      success: {
        background: vars.color.bgSurface,
        borderColor: vars.color.success,
      },
      error: {
        background: vars.color.bgSurface,
        borderColor: vars.color.danger,
      },
      warning: {
        background: vars.color.bgSurface,
        borderColor: vars.color.warning,
      },
      info: {
        background: vars.color.bgSurface,
        borderColor: vars.color.primary,
      },
    },
  },
  defaultVariants: { variant: 'info' },
})

export const toastIcon = recipe({
  base: { flexShrink: 0, marginTop: 1 },
  variants: {
    variant: {
      success: { color: vars.color.success },
      error: { color: vars.color.danger },
      warning: { color: vars.color.warning },
      info: { color: vars.color.primary },
    },
  },
})

export const toastBody = style({ flex: 1 })

export const toastTitle = style({
  fontWeight: 600,
  color: vars.color.textPrimary,
  lineHeight: 1.4,
})

export const toastDescription = style({
  color: vars.color.textMuted,
  marginTop: 2,
  fontSize: '12px',
  lineHeight: 1.4,
})

export const toastClose = style({
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: 0,
  color: vars.color.textMuted,
  flexShrink: 0,
  ':hover': { color: vars.color.textPrimary },
})
