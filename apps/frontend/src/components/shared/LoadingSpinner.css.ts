import { keyframes, style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

const spin = keyframes({
  to: { transform: 'rotate(360deg)' },
})

export const wrapper = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 40,
})

export const spinner = style({
  border: `3px solid ${vars.color.borderDefault}`,
  borderTopColor: vars.color.primary,
  borderRadius: vars.radius.full,
  animation: `${spin} 0.8s linear infinite`,
})
