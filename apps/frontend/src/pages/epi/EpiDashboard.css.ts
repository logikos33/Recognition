import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  minHeight: 0,
})

export const cameraSection = style({
  display: 'flex',
  flexDirection: 'column',
  background: '#000000', // allow: fundo preto absoluto do VMS (área de vídeo)
  overflow: 'hidden',
  position: 'relative',
  minHeight: '360px',
})

/* ── Grid BI de widgets (WS3 — substitui o layout de quadrantes) ── */

export const widgetGrid = style({
  display: 'grid',
  gridTemplateColumns: '1fr',
  gap: vars.space.md,
  padding: `${vars.space.md} ${vars.space.md} ${vars.space.md}`,
  '@media': {
    'screen and (min-width: 1100px)': {
      gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    },
  },
})

/** Widget largo (timeline) — ocupa as 2 colunas no desktop. */
export const widgetSpan2 = style({
  '@media': {
    'screen and (min-width: 1100px)': {
      gridColumn: 'span 2',
    },
  },
})
