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

/* Kept for classes panel and quick links — shown in a collapsible details section */
export const detailsPanel = style({
  padding: `${vars.space.md} ${vars.space.lg}`,
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
  background: vars.color.bgBase,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
})

export const classesPanel = style({
  background: vars.color.bgSurface,
  borderRadius: vars.radius.md,
  padding: vars.space.md,
})

export const classesPanelTitle = style({
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
  marginBottom: vars.space.sm,
})

export const classesGrid = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: vars.space.xs,
})

export const classChip = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  padding: '4px 10px',
  borderRadius: vars.radius.sm,
  fontSize: '11px',
})

export const classDot = style({
  width: '8px',
  height: '8px',
  borderRadius: vars.radius.full,
  flexShrink: 0,
})

export const className = style({
  color: vars.color.textPrimary,
  fontWeight: 500,
})

/* Placeholder for camera container before Entregável 3 */
export const cameraPlaceholder = style({
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: vars.color.textDim,
  fontSize: '14px',
  fontFamily: vars.font.mono,
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
