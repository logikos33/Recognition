import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const playerWrapper = style({
  position: 'relative',
  background: '#000', // allow: fundo do vídeo (sempre preto)
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

export const offlineOverlay = style([overlay, {
  flexDirection: 'column',
  gap: '10px',
  color: 'rgba(255,255,255,0.5)', // allow: overlay sobre vídeo preto
  fontFamily: vars.font.sans,
  fontSize: '13px',
}])

export const retryBtn = style({
  padding: '6px 16px',
  fontSize: '12px',
  fontWeight: 600,
  color: vars.color.textOnPrimary,
  background: vars.color.primary,
  border: `1px solid ${vars.color.primaryLight}`,
  borderRadius: '6px',
  cursor: 'pointer',
  ':hover': {
    background: vars.color.primaryDark,
  },
})
