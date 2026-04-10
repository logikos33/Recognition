import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const layout = style({
  display: 'flex',
  flexDirection: 'column',
  minHeight: '100vh',
  background: vars.color.bgPrimary,
})

export const mainContent = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'auto',
})
