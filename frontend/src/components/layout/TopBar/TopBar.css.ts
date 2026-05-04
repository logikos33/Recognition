import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const topBar = style({
  background: vars.color.bgSurface,
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  padding: `0 ${vars.space.lg}`,
  height: '52px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexShrink: 0,
  position: 'sticky',
  top: 0,
  zIndex: 40,
})

export const leftSection = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
})

export const hamburgerBtn = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '36px',
  height: '36px',
  borderRadius: vars.radius.md,
  background: 'transparent',
  border: 'none',
  color: vars.color.textSecondary,
  cursor: 'pointer',
  transition: `background ${vars.animation.duration} ${vars.animation.easing}, color ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
  },
})

export const logoLink = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  textDecoration: 'none',
})

export const logoEmoji = style({
  fontSize: '20px',
})

export const logoText = style({
  fontWeight: 700,
  fontSize: '15px',
  color: vars.color.textPrimary,
  letterSpacing: '-0.01em',
})

export const breadcrumb = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
  fontSize: '13px',
  color: vars.color.textMuted,
})

export const breadcrumbSep = style({
  color: vars.color.textDim,
  userSelect: 'none',
})

export const breadcrumbCurrent = style({
  color: vars.color.textSecondary,
  fontWeight: 600,
})

export const rightSection = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
})

export const userInfo = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
})

export const userName = style({
  fontSize: '13px',
  color: vars.color.textSecondary,
})

export const roleBadge = style({
  padding: '2px 8px',
  borderRadius: vars.radius.sm,
  fontSize: '10px',
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
})

export const logoutButton = style({
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textMuted,
  background: 'transparent',
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  padding: '5px 12px',
  cursor: 'pointer',
  transition: `color ${vars.animation.duration}, border-color ${vars.animation.duration}`,
  ':hover': {
    color: vars.color.textPrimary,
    borderColor: vars.color.borderStrong,
  },
})
