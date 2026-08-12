import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const wrapper = style({
  position: 'relative',
  display: 'inline-flex',
  width: 120,
  height: 68,
  borderRadius: vars.radius.md,
  overflow: 'hidden',
  background: '#0d0f12', // allow: placeholder de miniatura de câmera (sempre escuro)
  border: `1px solid ${vars.color.borderDefault}`,
})

export const imageButton = style({
  all: 'unset',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
  height: '100%',
  cursor: 'pointer',
  selectors: {
    '&:disabled': { cursor: 'default' },
  },
})

export const image = style({
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
})

export const statusText = style({
  fontSize: '10px',
  lineHeight: 1.3,
  padding: '4px 6px',
  textAlign: 'center',
  color: 'rgba(255,255,255,0.65)', // allow: texto sobre fundo escuro de miniatura
})

export const failedText = style([statusText, {
  color: vars.color.danger,
}])

export const capturedBadge = style({
  position: 'absolute',
  bottom: 2,
  left: 4,
  right: 4,
  fontSize: '9px',
  color: 'rgba(255,255,255,0.85)', // allow: badge sobre imagem de câmera
  textShadow: '0 1px 2px rgba(0,0,0,0.9)', // allow: legibilidade sobre imagem qualquer
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
})

export const failedBadge = style([capturedBadge, {
  color: '#fff', // allow: badge de falha sobre imagem qualquer
  background: 'rgba(185,28,28,0.85)', // allow: fundo de alerta sobre imagem qualquer
  textShadow: 'none',
  borderRadius: vars.radius.sm,
  padding: '1px 4px',
  bottom: 2,
  left: 2,
  right: 2,
}])

export const refreshBtn = style({
  position: 'absolute',
  top: 2,
  right: 2,
  width: 18,
  height: 18,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: vars.radius.sm,
  border: 'none',
  background: 'rgba(0,0,0,0.55)', // allow: botão sobreposto à miniatura
  color: '#fff', // allow: ícone sobre fundo escuro do botão
  cursor: 'pointer',
  fontSize: '11px',
  lineHeight: 1,
  selectors: {
    '&:disabled': { opacity: 0.5, cursor: 'default' },
    '&:hover:not(:disabled)': { background: 'rgba(0,0,0,0.75)' },
  },
})

export const enlargedWrap = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: vars.space.sm,
})

export const enlargedImage = style({
  maxWidth: '100%',
  maxHeight: '60vh',
  borderRadius: vars.radius.md,
  background: '#0d0f12', // allow: placeholder de imagem ampliada
})

export const enlargedPlaceholder = style({
  width: 480,
  height: 270,
  maxWidth: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: vars.radius.md,
  background: '#0d0f12', // allow: placeholder de imagem ampliada
  color: 'rgba(255,255,255,0.6)', // allow: texto sobre placeholder escuro
  fontSize: '13px',
  textAlign: 'center',
  padding: vars.space.md,
})

export const enlargedMeta = style({
  fontSize: '12px',
  color: vars.color.textMuted,
})
