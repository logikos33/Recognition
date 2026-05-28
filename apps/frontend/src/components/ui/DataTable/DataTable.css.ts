import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const wrapper = style({
  width: '100%',
  overflowX: 'auto',
})

export const table = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontFamily: vars.font.sans,
  fontSize: '13px',
})

export const thead = style({
  borderBottom: `1px solid ${vars.color.borderDefault}`,
})

export const th = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '11px',
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  color: vars.color.textMuted,
  userSelect: 'none',
  whiteSpace: 'nowrap',
})

export const thSortable = style([th, {
  cursor: 'pointer',
  ':hover': { color: vars.color.textSecondary },
}])

export const td = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  color: vars.color.textSecondary,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  verticalAlign: 'middle',
})

export const tr = style({
  transition: `background ${vars.animation.duration} ${vars.animation.easing}`,
  ':hover': { background: vars.color.bgHover },
})

export const paginationRow = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.sm,
  padding: `${vars.space.sm} ${vars.space.md}`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  fontFamily: vars.font.sans,
  fontSize: '12px',
  color: vars.color.textMuted,
})
