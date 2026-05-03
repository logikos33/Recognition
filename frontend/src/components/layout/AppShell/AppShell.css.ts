import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const root = style({
  minHeight: '100vh',
  background: vars.color.bgBase,
  color: vars.color.textPrimary,
  fontFamily: vars.font.sans,
  display: 'flex',
  flexDirection: 'column',
  transition: 'background-color 0.35s ease',
})
