/**
 * widgets.css — estilos dos widgets BI do dashboard (mutirão WS3).
 * Somente tokens do tema — zero cor hardcoded.
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

/* ── Shell ──────────────────────────────────────────────────────── */

export const shellWrap = style({
  display: 'flex',
  flexDirection: 'column',
  minWidth: 0,
})

export const widgetTitleRow = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: vars.space.xs,
})

export const infoIcon = style({
  display: 'inline-flex',
  alignItems: 'center',
  color: vars.color.textDim,
  cursor: 'help',
})

export const widgetActions = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
})

export const iconButton = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '26px',
  height: '26px',
  padding: 0,
  background: 'transparent',
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.sm,
  color: vars.color.textMuted,
  cursor: 'pointer',
  selectors: {
    '&:hover': {
      color: vars.color.textPrimary,
      borderColor: vars.color.borderDefault,
    },
  },
})

export const dragHandle = style([
  iconButton,
  {
    cursor: 'grab',
    selectors: {
      '&:active': { cursor: 'grabbing' },
    },
  },
])

export const widgetBody = style({
  display: 'flex',
  flexDirection: 'column',
  minHeight: '220px',
})

/* ── Estados (loading / erro / vazio) ───────────────────────────── */

export const stateBox = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: vars.space.sm,
  minHeight: '180px',
  padding: vars.space.md,
})

export const errorText = style({
  fontSize: '13px',
  color: vars.color.danger,
  textAlign: 'center',
})

/* ── Gráficos ───────────────────────────────────────────────────── */

export const chartWrap = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  minHeight: 0,
})

export const legendList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  marginTop: vars.space.sm,
})

export const legendRow = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '12px',
  color: vars.color.textSecondary,
})

export const legendDot = style({
  width: '10px',
  height: '10px',
  borderRadius: vars.radius.full,
  flexShrink: 0,
})

export const legendName = style({
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const legendValue = style({
  fontWeight: 600,
  color: vars.color.textPrimary,
})

/* ── Listas / tabela (migrado dos quadrantes do EpiDashboard) ───── */

export const alertList = style({
  flex: 1,
  minHeight: 0,
})

export const alertRow = style({
  display: 'flex',
  gap: vars.space.sm,
  padding: `${vars.space.xs} 0`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  alignItems: 'flex-start',
})

export const alertRowBody = style({
  flex: 1,
  minWidth: 0,
})

export const alertRowCamera = style({
  fontSize: '13px',
  fontWeight: 600,
  color: vars.color.textPrimary,
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

export const eventTableWrap = style({
  flex: 1,
  overflowY: 'auto',
  minHeight: 0,
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

export const eventRowAcknowledged = style({
  opacity: 0.5,
})
