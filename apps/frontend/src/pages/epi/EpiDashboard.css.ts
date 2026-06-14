import { style } from '@vanilla-extract/css'
import { vars } from '../../styles/theme.css'

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  overflow: 'hidden',
})

export const cameraSection = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  background: '#000000',
  overflow: 'hidden',
  position: 'relative',
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

/* ── 4-quadrant layout ──────────────────────────────────────────── */

export const quadrantGrid = style({
  display: 'grid',
  gridTemplateColumns: '3fr 2fr',
  gap: vars.space.md,
  marginTop: vars.space.md,
  padding: `0 ${vars.space.md} ${vars.space.md}`,
})

export const quadrant = style({
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.lg,
  padding: vars.space.md,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  minHeight: '240px',
})

export const quadrantTitle = style({
  fontSize: '13px',
  fontWeight: 700,
  color: vars.color.textSecondary,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  marginBottom: vars.space.sm,
  flexShrink: 0,
})

export const alertRow = style({
  display: 'flex',
  gap: vars.space.sm,
  padding: `${vars.space.xs} 0`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  alignItems: 'flex-start',
})

export const alertRowCamera = style({
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const alertRowViolation = style({
  fontSize: '12px',
  color: vars.color.textSecondary,
})

export const alertRowTime = style({
  fontSize: '11px',
  color: vars.color.textDim,
  flexShrink: 0,
})

export const viewAllLink = style({
  display: 'block',
  textAlign: 'center',
  fontSize: '12px',
  color: vars.color.primary,
  textDecoration: 'none',
  marginTop: vars.space.sm,
  paddingTop: vars.space.sm,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  flexShrink: 0,
})

export const eventTable = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '12px',
})

export const eventTh = style({
  textAlign: 'left',
  padding: `${vars.space.xs} ${vars.space.sm}`,
  fontSize: '10px',
  fontWeight: 700,
  color: vars.color.textDim,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  borderBottom: `1px solid ${vars.color.borderDefault}`,
})

export const eventTd = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  color: vars.color.textSecondary,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  verticalAlign: 'top',
})

export const chartWrap = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  minHeight: 0,
})

export const emptyQuadrant = style({
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: vars.color.textDim,
  fontSize: '13px',
})
