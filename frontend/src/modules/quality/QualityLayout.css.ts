/**
 * Módulo de Qualidade — Layout styles.
 * Vanilla Extract CSS-in-TS com tokens do theme contract.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const layoutRoot = style({
  display: 'flex',
  flexDirection: 'column',
  minHeight: '100vh',
  background: vars.color.bgPrimary,
})

export const topBar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.lg,
  padding: `${vars.space.sm} ${vars.space.xl}`,
  background: vars.color.bgSurface,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  position: 'sticky',
  top: 0,
  zIndex: 10,
})

export const topBarTitle = style({
  fontSize: '14px',
  fontWeight: '700',
  color: vars.color.textPrimary,
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
})

export const nav = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
  flex: 1,
})

export const navLink = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  borderRadius: vars.radius.sm,
  fontSize: '13px',
  fontWeight: '500',
  color: vars.color.textSecondary,
  textDecoration: 'none',
  transition: 'color 0.15s, background 0.15s',
  ':hover': {
    color: vars.color.textPrimary,
    background: vars.color.bgHover,
  },
})

export const navLinkActive = style([navLink, {
  color: vars.color.textPrimary,
  background: vars.color.bgElevated,
  fontWeight: '600',
}])

export const main = style({
  flex: 1,
  overflow: 'auto',
})

