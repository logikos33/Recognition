import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const header = style({
  background: vars.color.bgSurface,
  borderBottom: `1px solid ${vars.color.borderDefault}`,
  padding: `10px ${vars.space.lg}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexShrink: 0,
  position: 'sticky',
  top: 0,
  zIndex: 40,
})

export const left = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.lg,
})

export const logoLink = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  textDecoration: 'none',
  flexShrink: 0,
})

export const logoText = style({
  fontWeight: 700,
  fontSize: '15px',
  color: vars.color.textPrimary,
  letterSpacing: '-0.01em',
})

export const nav = style({
  display: 'flex',
  gap: '2px',
})

export const navLink = style({
  padding: `6px ${vars.space.md}`,
  borderRadius: vars.radius.md,
  fontSize: '13px',
  fontWeight: 600,
  textDecoration: 'none',
  color: vars.color.textSecondary,
  transition: `background ${vars.animation.duration} ${vars.animation.easing}, color ${vars.animation.duration}`,
  ':hover': {
    background: vars.color.bgHover,
    color: vars.color.textPrimary,
  },
})

export const navLinkActive = style([navLink, {
  background: vars.color.purple600,
  color: '#fff',
  ':hover': {
    background: vars.color.purple500,
    color: '#fff',
  },
}])

export const right = style({
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

export const logoEmoji = style({
  fontSize: '20px',
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
