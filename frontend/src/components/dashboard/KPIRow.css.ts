import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const row = style({
  display: 'flex',
  gap: vars.space.md,
  padding: `${vars.space.md} ${vars.space.lg}`,
  overflowX: 'auto',
  flexShrink: 0,
  '@media': {
    '(max-width: 768px)': {
      padding: `${vars.space.sm} ${vars.space.md}`,
      gap: vars.space.sm,
    },
  },
})

export const drawer = style({
  margin: `0 ${vars.space.lg} ${vars.space.sm}`,
  padding: vars.space.md,
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
})

export const drawerTitle = style({
  fontSize: '12px',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: vars.color.textMuted,
})

export const drawerList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const drawerItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
  padding: `4px ${vars.space.sm}`,
  fontSize: '12px',
  color: vars.color.textSecondary,
  borderRadius: vars.radius.sm,
  background: vars.color.bgSurface,
})

export const drawerLink = style({
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.purple400,
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: 0,
  alignSelf: 'flex-start',
  ':hover': {
    color: vars.color.purple400,
  },
})
