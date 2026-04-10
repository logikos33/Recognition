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
