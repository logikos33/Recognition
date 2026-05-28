import { style } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../styles/theme.css'

export const empty = style({
  padding: vars.space.md,
  color: vars.color.textMuted,
  fontSize: '14px',
})

export const list = style({
  maxHeight: '400px',
  overflowY: 'auto',
})

export const alertRow = recipe({
  base: {
    padding: '12px 16px',
    borderBottom: `1px solid ${vars.color.borderDefault}`,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  variants: {
    acknowledged: {
      true: { background: 'transparent' },
      false: { background: vars.color.bgElevated },
    },
  },
})

export const alertBody = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
})

export const violationText = style({
  color: vars.color.danger,
  fontSize: '13px',
  fontWeight: 500,
})

export const timestampText = style({
  color: vars.color.textMuted,
  fontSize: '12px',
})
