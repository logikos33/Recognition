/**
 * Admin module layout styles — Vanilla Extract CSS-in-TS.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const adminRoot = style({
  display: 'flex',
  minHeight: '100vh',
  background: vars.color.bgBase,
  '@media': {
    '(max-width: 768px)': {
      flexDirection: 'column',
    },
  },
})

// ── Mobile topbar ─────────────────────────────────────────────────────────────

export const mobileTopbar = style({
  display: 'none',
  '@media': {
    '(max-width: 768px)': {
      display: 'flex',
      alignItems: 'center',
      gap: vars.space.sm,
      padding: `${vars.space.sm} ${vars.space.md}`,
      background: vars.color.bgSurface,
      borderBottom: `1px solid ${vars.color.borderSubtle}`,
      position: 'sticky',
      top: 0,
      zIndex: 50,
      width: '100%',
    },
  },
})

export const mobileTopbarTitle = style({
  fontSize: '13px',
  fontWeight: '700',
  color: vars.color.textPrimary,
  flex: 1,
})

export const hamburgerBtn = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: vars.color.textSecondary,
  padding: vars.space.xs,
  borderRadius: vars.radius.sm,
  ':hover': {
    color: vars.color.textPrimary,
    background: vars.color.bgHover,
  },
})

// ── Sidebar overlay (mobile backdrop) ─────────────────────────────────────────

export const sidebarOverlay = style({
  display: 'none',
  '@media': {
    '(max-width: 768px)': {
      display: 'block',
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.5)',
      zIndex: 99,
    },
  },
})

// ── Sidebar ───────────────────────────────────────────────────────────────────

export const sidebar = style({
  width: '220px',
  minWidth: '220px',
  background: vars.color.bgSurface,
  borderRight: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  flexDirection: 'column',
  position: 'sticky',
  top: 0,
  height: '100vh',
  overflow: 'hidden',
  '@media': {
    '(max-width: 768px)': {
      position: 'fixed',
      top: 0,
      left: 0,
      height: '100vh',
      zIndex: 100,
      transform: 'translateX(-100%)',
      transition: `transform ${vars.animation.duration} ease`,
      boxShadow: vars.shadow.lg,
    },
  },
})

export const sidebarOpenClass = style({
  '@media': {
    '(max-width: 768px)': {
      transform: 'translateX(0)',
    },
  },
})

export const sidebarHeader = style({
  padding: `${vars.space.lg} ${vars.space.md}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
})

export const sidebarHeaderText = style({
  flex: 1,
})

export const sidebarTitle = style({
  fontSize: '13px',
  fontWeight: '700',
  color: vars.color.textPrimary,
  marginBottom: vars.space.xs,
})

export const sidebarSubtitle = style({
  fontSize: '11px',
  color: vars.color.textMuted,
})

export const sidebarCloseBtn = style({
  display: 'none',
  '@media': {
    '(max-width: 768px)': {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      color: vars.color.textMuted,
      padding: vars.space.xs,
      borderRadius: vars.radius.sm,
      ':hover': {
        color: vars.color.textPrimary,
      },
    },
  },
})

export const sidebarNav = style({
  flex: 1,
  padding: `${vars.space.sm} 0`,
  overflowY: 'auto',
})

export const sidebarGroup = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
})

export const sidebarGroupLabel = style({
  fontSize: '10px',
  fontWeight: '600',
  color: vars.color.textMuted,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  padding: `${vars.space.xs} ${vars.space.sm}`,
  marginBottom: vars.space.xs,
})

export const navItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `7px ${vars.space.sm}`,
  borderRadius: vars.radius.sm,
  fontSize: '13px',
  fontWeight: '500',
  color: vars.color.textSecondary,
  textDecoration: 'none',
  cursor: 'pointer',
  transition: `color ${vars.animation.duration}, background ${vars.animation.duration}`,
  position: 'relative',
  ':hover': {
    color: vars.color.textPrimary,
    background: vars.color.bgHover,
  },
})

export const navItemActive = style([navItem, {
  color: vars.color.textPrimary,
  background: vars.color.bgElevated,
  fontWeight: '600',
}])

export const navItemExternal = style([navItem, {
  ':after': {
    content: '""',
  },
}])

export const navBadge = style({
  marginLeft: 'auto',
  background: vars.color.danger,
  color: '#fff',
  fontSize: '10px',
  fontWeight: '700',
  padding: '1px 5px',
  borderRadius: vars.radius.full,
  minWidth: '16px',
  textAlign: 'center',
})

export const sidebarFooter = style({
  padding: vars.space.md,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
})

export const backButton = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
  fontSize: '12px',
  color: vars.color.textMuted,
  textDecoration: 'none',
  padding: `${vars.space.xs} ${vars.space.sm}`,
  borderRadius: vars.radius.sm,
  transition: `color ${vars.animation.duration}`,
  ':hover': {
    color: vars.color.textPrimary,
  },
})

export const mainContent = style({
  flex: 1,
  overflow: 'auto',
  display: 'flex',
  flexDirection: 'column',
  '@media': {
    '(max-width: 768px)': {
      width: '100%',
    },
  },
})
