import { style, keyframes } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

const fadeIn = keyframes({
  from: { opacity: 0 },
  to: { opacity: 1 },
})

const slideUp = keyframes({
  from: { opacity: 0, transform: 'translateY(16px)' },
  to: { opacity: 1, transform: 'translateY(0)' },
})

export const overlay = style({
  position: 'fixed',
  inset: 0,
  zIndex: 100,
  background: 'rgba(0, 0, 0, 0.93)',
  display: 'flex',
  alignItems: 'stretch',
  animationName: fadeIn,
  animationDuration: '180ms',
  animationTimingFunction: 'ease-out',
  animationFillMode: 'both',
})

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  width: '100%',
  height: '100%',
  animationName: slideUp,
  animationDuration: '220ms',
  animationTimingFunction: 'ease-out',
  animationFillMode: 'both',
})

/* Header */
export const header = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
  padding: `${vars.space.sm} ${vars.space.lg}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
  background: 'rgba(0, 0, 0, 0.45)',
})

export const videoName = style({
  color: vars.color.textPrimary,
  fontWeight: 600,
  fontSize: '14px',
  flex: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const frameCount = style({
  color: vars.color.textMuted,
  fontSize: '13px',
  flexShrink: 0,
})

export const headerActions = style({
  display: 'flex',
  gap: vars.space.sm,
  alignItems: 'center',
  flexShrink: 0,
})

export const actionBtn = style({
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  padding: `5px ${vars.space.md}`,
  background: 'transparent',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  color: vars.color.textSecondary,
  fontSize: '12px',
  fontWeight: 600,
  cursor: 'pointer',
  transition: 'border-color 180ms, color 180ms',
  ':hover': {
    borderColor: vars.color.cyan400,
    color: vars.color.cyan400,
  },
})

export const actionBtnPrimary = style({
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  padding: `5px ${vars.space.md}`,
  background: vars.color.purple500,
  border: `1px solid ${vars.color.purple500}`,
  borderRadius: vars.radius.md,
  color: '#fff',
  fontSize: '12px',
  fontWeight: 600,
  cursor: 'pointer',
  transition: 'background 180ms',
  ':hover': {
    background: vars.color.purple600,
  },
})

export const closeBtn = style({
  background: 'none',
  border: 'none',
  color: vars.color.textMuted,
  cursor: 'pointer',
  padding: '4px',
  borderRadius: vars.radius.sm,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'color 180ms',
  ':hover': {
    color: vars.color.textPrimary,
  },
})

/* Preview area (70% height) */
export const preview = style({
  flex: '1 1 0',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  position: 'relative',
  minHeight: 0,
  overflow: 'hidden',
})

export const navBtn = style({
  position: 'absolute',
  top: '50%',
  transform: 'translateY(-50%)',
  zIndex: 2,
  background: 'rgba(0, 0, 0, 0.55)',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  padding: vars.space.sm,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'background 180ms, opacity 180ms',
  ':hover': {
    background: 'rgba(0, 0, 0, 0.85)',
  },
  ':disabled': {
    opacity: 0.2,
    cursor: 'default',
    pointerEvents: 'none',
  },
})

export const navBtnLeft = style({
  left: vars.space.lg,
})

export const navBtnRight = style({
  right: vars.space.lg,
})

export const previewImageWrap = style({
  position: 'relative',
  maxHeight: '100%',
  maxWidth: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: vars.space.md,
})

export const previewImage = style({
  maxHeight: '100%',
  maxWidth: '100%',
  objectFit: 'contain',
  borderRadius: vars.radius.md,
  display: 'block',
})

export const previewBadge = style({
  position: 'absolute',
  top: vars.space.md,
  left: vars.space.md,
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  background: 'rgba(0, 0, 0, 0.65)',
  padding: '3px 10px',
  borderRadius: vars.radius.full,
  backdropFilter: 'blur(4px)',
})

export const previewBadgeLabel = style({
  color: vars.color.textSecondary,
  fontSize: '11px',
})

/* Timeline strip (30% height) */
export const timeline = style({
  flex: '0 0 118px',
  display: 'flex',
  gap: '4px',
  overflowX: 'auto',
  padding: `${vars.space.sm} ${vars.space.lg}`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  background: 'rgba(0, 0, 0, 0.5)',
  scrollbarWidth: 'thin',
  scrollbarColor: `${vars.color.borderDefault} transparent`,
  alignItems: 'center',
})

export const thumb = style({
  flexShrink: 0,
  position: 'relative',
  width: '82px',
  height: '56px',
  background: 'none',
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: '4px',
  padding: 0,
  cursor: 'pointer',
  overflow: 'hidden',
  transition: 'border-color 150ms',
  ':hover': {
    borderColor: vars.color.purple400,
  },
})

export const thumbActive = style({
  borderColor: `${vars.color.purple500} !important` as any,
  boxShadow: `0 0 0 1px ${vars.color.purple500}`,
})

export const thumbImg = style({
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
})

export const thumbBadgeWrap = style({
  position: 'absolute',
  top: '2px',
  right: '2px',
  fontSize: '9px',
  lineHeight: 1,
  pointerEvents: 'none',
})

export const thumbActiveBar = style({
  position: 'absolute',
  bottom: 0,
  left: 0,
  right: 0,
  height: '3px',
  background: vars.color.purple500,
  pointerEvents: 'none',
})

/* Keyboard hint */
export const hint = style({
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  gap: vars.space.md,
  padding: '5px',
  flexShrink: 0,
  color: vars.color.textMuted,
  fontSize: '11px',
  letterSpacing: '0.02em',
})

/* Annotation status badges */
export const badgeAnnotated = style({
  color: vars.color.success,
  fontSize: '11px',
})

export const badgePreAnnotated = style({
  color: vars.color.cyan400,
  fontSize: '11px',
})

export const badgeEmpty = style({
  color: vars.color.textDim,
  fontSize: '11px',
  opacity: 0.6,
})
