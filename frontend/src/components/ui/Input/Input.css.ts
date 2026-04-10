import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const input = style({
  width: '100%',
  fontFamily: vars.font.sans,
  fontSize: '14px',
  color: vars.color.textPrimary,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: vars.radius.md,
  padding: `9px ${vars.space.md}`,
  transition: `border-color ${vars.animation.duration} ${vars.animation.easing}`,
  '::placeholder': {
    color: vars.color.textDim,
  },
  ':focus': {
    borderColor: vars.color.purple500,
  },
  ':disabled': {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
})

export const inputError = style([input, {
  borderColor: vars.color.danger,
  ':focus': {
    borderColor: vars.color.danger,
  },
}])

export const label = style({
  display: 'block',
  fontFamily: vars.font.sans,
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textSecondary,
  marginBottom: '5px',
  letterSpacing: '0.03em',
})

export const errorText = style({
  fontFamily: vars.font.sans,
  fontSize: '11px',
  color: vars.color.danger,
  marginTop: '4px',
})

export const fieldWrapper = style({
  display: 'flex',
  flexDirection: 'column',
})
