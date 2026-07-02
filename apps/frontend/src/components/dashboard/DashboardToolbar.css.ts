/**
 * DashboardToolbar — seletor de período + popover Personalizar (WS3).
 * Somente tokens do tema.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const toolbar = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.md,
  padding: `${vars.space.md} ${vars.space.md} 0`,
  flexWrap: 'wrap',
})

export const toolbarLabel = style({
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.textSecondary,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
})

export const toolbarRight = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
})

export const segmented = style({
  display: 'inline-flex',
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.md,
  padding: '2px',
  gap: '2px',
})

export const segmentButton = style({
  padding: '4px 12px',
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textMuted,
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.sm,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  selectors: {
    '&:hover': { color: vars.color.textPrimary },
  },
})

export const segmentButtonActive = style({
  background: vars.color.primaryAlpha,
  color: vars.color.primary,
})

export const popoverBody = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  minWidth: '240px',
  padding: vars.space.xs,
})

export const popoverTitle = style({
  fontSize: '12px',
  fontWeight: 700,
  color: vars.color.textSecondary,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
})

export const checkRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  fontSize: '13px',
  color: vars.color.textPrimary,
  cursor: 'pointer',
  padding: `2px 0`,
})

export const checkInput = style({
  accentColor: vars.color.primary,
  cursor: 'pointer',
})

export const popoverFooter = style({
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  paddingTop: vars.space.sm,
  display: 'flex',
  justifyContent: 'flex-end',
})
