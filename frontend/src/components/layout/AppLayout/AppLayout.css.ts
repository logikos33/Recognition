import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const layout = style({
  display: 'flex',
  flexDirection: 'column',
  minHeight: '100vh',
  background: vars.color.bgBase,
})

export const mainContent = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'auto',
  '@media': {
    '(min-width: 768px) and (max-width: 1023px)': {
      marginLeft: '60px',
    },
    '(min-width: 1024px)': {
      marginLeft: '280px',
    },
  },
})
