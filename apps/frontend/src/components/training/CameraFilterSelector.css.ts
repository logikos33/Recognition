/**
 * CameraFilterSelector styles — seletor recolhido de câmera (popover +
 * checkboxes) do filtro de treinamento.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const trigger = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '4px 12px',
  borderRadius: vars.radius.full,
  fontSize: '12px',
  fontWeight: 600,
  cursor: 'pointer',
  border: `1px solid ${vars.color.borderDefault}`,
  background: 'transparent',
  color: vars.color.textSecondary,
  whiteSpace: 'nowrap',
  selectors: {
    '&:hover': { background: vars.color.bgHover },
  },
})

export const panel = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  width: '280px',
})

export const searchWrap = style({
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
})

export const searchIcon = style({
  position: 'absolute',
  left: '8px',
  color: vars.color.textMuted,
  pointerEvents: 'none',
})

export const searchInput = style({
  width: '100%',
  padding: '6px 8px 6px 26px',
  fontSize: '12px',
  fontFamily: vars.font.sans,
  color: vars.color.textPrimary,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.sm,
  outline: 'none',
  selectors: {
    '&:focus': { borderColor: vars.color.primary },
    '&::placeholder': { color: vars.color.textMuted },
  },
})

export const quickActions = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  paddingBottom: vars.space.xs,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
})

export const quickAction = style({
  fontSize: '11px',
  fontWeight: 700,
  letterSpacing: '0.02em',
  textTransform: 'uppercase',
  color: vars.color.primary,
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: '2px 0',
  selectors: {
    '&:hover': { textDecoration: 'underline' },
  },
})

export const list = style({
  display: 'flex',
  flexDirection: 'column',
  maxHeight: '288px',
  overflowY: 'auto',
})

export const row = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.sm,
  padding: '5px 4px',
  fontSize: '12px',
  color: vars.color.textPrimary,
  cursor: 'pointer',
  borderRadius: vars.radius.sm,
  selectors: {
    '&:hover': { background: vars.color.bgHover },
  },
})

export const rowLeft = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  minWidth: 0,
  flex: 1,
})

export const checkbox = style({
  accentColor: vars.color.primary,
  cursor: 'pointer',
  flexShrink: 0,
})

export const channel = style({
  fontFamily: vars.font.mono,
  fontSize: '11px',
  color: vars.color.textMuted,
  flexShrink: 0,
  minWidth: '16px',
})

export const name = style({
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const count = style({
  fontFamily: vars.font.mono,
  fontSize: '11px',
  color: vars.color.textMuted,
  flexShrink: 0,
})

export const empty = style({
  fontSize: '12px',
  color: vars.color.textMuted,
  padding: '10px 4px',
  textAlign: 'center',
})
