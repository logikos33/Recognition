import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const bellWrap = style({
  position: 'relative',
  display: 'inline-flex',
})

export const bellBtn = style({
  width: '36px',
  height: '36px',
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: vars.radius.md,
  transition: `background ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': {
    background: vars.color.bgHover,
  },
})

export const badge = style({
  position: 'absolute',
  top: 0,
  right: 0,
  minWidth: '16px',
  height: '16px',
  borderRadius: vars.radius.full,
  background: vars.color.danger,
  color: '#fff',
  fontSize: '10px',
  fontWeight: 700,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '0 3px',
  pointerEvents: 'none',
  transform: 'translate(4px, -4px)',
})

export const panel = style({
  position: 'fixed',
  top: '60px',
  right: '16px',
  width: '360px',
  maxHeight: '480px',
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.lg,
  boxShadow: vars.shadow.lg,
  zIndex: 200,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
})

export const panelHeader = style({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: `${vars.space.sm} ${vars.space.md}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
})

export const panelTitle = style({
  fontSize: '14px',
  fontWeight: 600,
  color: vars.color.textPrimary,
})

export const panelBody = style({
  flex: 1,
  overflowY: 'auto',
})

export const alertCard = style({
  display: 'flex',
  gap: vars.space.sm,
  padding: `${vars.space.sm} ${vars.space.md}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  cursor: 'pointer',
  transition: `background ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': {
    background: vars.color.bgHover,
  },
})

export const alertIcon = style({
  width: '20px',
  flexShrink: 0,
  paddingTop: '2px',
})

export const alertContent = style({
  flex: 1,
  minWidth: 0,
})

export const alertCamera = style({
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const alertViolation = style({
  fontSize: '12px',
  color: vars.color.textSecondary,
  marginTop: '2px',
})

export const alertTime = style({
  fontSize: '11px',
  color: vars.color.textDim,
  marginTop: '2px',
})

export const emptyPanel = style({
  padding: '32px 16px',
  textAlign: 'center',
  color: vars.color.textMuted,
  fontSize: '13px',
})

export const viewAllBtn = style({
  display: 'block',
  width: '100%',
  padding: `${vars.space.sm} ${vars.space.md}`,
  textAlign: 'center',
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.primary,
  background: 'transparent',
  border: 'none',
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  cursor: 'pointer',
  flexShrink: 0,
  transition: `background ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': {
    background: vars.color.bgHover,
  },
})
