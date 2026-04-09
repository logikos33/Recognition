import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const playerWrapper = style({
  position: 'relative',
  background: '#000',
  overflow: 'hidden',
  borderRadius: vars.radius.md,
})

export const video = style({
  width: '100%',
  height: '100%',
  objectFit: 'contain',
  display: 'block',
})

export const overlay = style({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 2,
})

export const connectingText = style([overlay, {
  color: vars.color.textSecondary,
  fontFamily: vars.font.sans,
  fontSize: '13px',
}])

export const errorText = style([overlay, {
  color: vars.color.danger,
  fontFamily: vars.font.sans,
  fontSize: '13px',
}])
