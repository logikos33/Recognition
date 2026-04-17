/**
 * Módulo de Qualidade — Estilos compartilhados entre componentes.
 * Vanilla Extract CSS-in-TS. Usa vars.color.*, vars.space.*, vars.radius.* do theme contract.
 */
import { style, styleVariants } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

// ── Layout base ───────────────────────────────────────────────────────────────

export const card = style({
  background: vars.color.bgSurface,
  borderRadius: vars.radius.md,
  border: `1px solid ${vars.color.borderSubtle}`,
  padding: vars.space.md,
})

export const cardHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: vars.space.sm,
})

export const cardTitle = style({
  fontSize: '11px',
  fontWeight: '600',
  color: vars.color.textSecondary,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
})

export const cardValue = style({
  fontSize: '28px',
  fontWeight: '700',
  color: vars.color.textPrimary,
})

// ── Badges de resultado ────────────────────────────────────────────────────────

const badgeBase = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: vars.space.xs,
  padding: `2px 8px`,
  borderRadius: vars.radius.full,
  fontSize: '11px',
  fontWeight: '600',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
})

export const badge = badgeBase

export const badgeVariants = styleVariants({
  ok: [badgeBase, {
    background: 'rgba(67,209,134,0.12)',
    color: '#43D186',
    border: '1px solid rgba(67,209,134,0.25)',
  }],
  nok: [badgeBase, {
    background: 'rgba(239,83,80,0.12)',
    color: '#EF5350',
    border: '1px solid rgba(239,83,80,0.25)',
  }],
  pending: [badgeBase, {
    background: 'rgba(255,183,77,0.12)',
    color: '#FFB74D',
    border: '1px solid rgba(255,183,77,0.25)',
  }],
  confirmed: [badgeBase, {
    background: 'rgba(79,195,247,0.12)',
    color: '#4FC3F7',
    border: '1px solid rgba(79,195,247,0.25)',
  }],
  rejected: [badgeBase, {
    background: 'rgba(206,147,216,0.12)',
    color: '#CE93D8',
    border: '1px solid rgba(206,147,216,0.25)',
  }],
})

// ── Tabela ────────────────────────────────────────────────────────────────────

export const table = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '13px',
})

export const th = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  textAlign: 'left',
  fontWeight: '600',
  color: vars.color.textSecondary,
  fontSize: '11px',
  textTransform: 'uppercase',
  borderBottom: `1px solid ${vars.color.borderDefault}`,
})

export const td = style({
  padding: `${vars.space.sm} ${vars.space.sm}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  color: vars.color.textPrimary,
})

export const trHover = style({
  ':hover': {
    background: vars.color.bgHover,
    cursor: 'pointer',
  },
})

// ── Métricas bar ──────────────────────────────────────────────────────────────

export const metricsBar = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: vars.space.sm,
})

export const metricItem = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
  padding: vars.space.sm,
  background: vars.color.bgCard,
  borderRadius: vars.radius.md,
})

export const metricLabel = style({
  fontSize: '11px',
  color: vars.color.textSecondary,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
})

export const metricValue = style({
  fontSize: '24px',
  fontWeight: '700',
  color: vars.color.textPrimary,
})

export const metricValueOk = style([metricValue, { color: '#43D186' }])
export const metricValueNok = style([metricValue, { color: '#EF5350' }])

// ── Barra de progresso ────────────────────────────────────────────────────────

export const progressBar = style({
  width: '100%',
  height: '6px',
  background: vars.color.borderDefault,
  borderRadius: vars.radius.full,
  overflow: 'hidden',
})

export const progressFill = style({
  height: '100%',
  borderRadius: vars.radius.full,
  transition: 'width 0.3s ease',
})

// ── Pareto chart ──────────────────────────────────────────────────────────────

export const paretoBar = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
  marginBottom: vars.space.xs,
})

export const paretoLabel = style({
  fontSize: '12px',
  color: vars.color.textSecondary,
  minWidth: '120px',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const paretoCount = style({
  fontSize: '12px',
  fontWeight: '600',
  color: vars.color.textPrimary,
  minWidth: '30px',
  textAlign: 'right',
})

// ── Annotation canvas ─────────────────────────────────────────────────────────

export const canvasContainer = style({
  position: 'relative',
  userSelect: 'none',
  cursor: 'crosshair',
  overflow: 'hidden',
  borderRadius: vars.radius.md,
  background: vars.color.bgCard,
})

export const canvasImage = style({
  display: 'block',
  width: '100%',
  height: 'auto',
  pointerEvents: 'none',
})

export const bboxOverlay = style({
  position: 'absolute',
  top: 0,
  left: 0,
  width: '100%',
  height: '100%',
  pointerEvents: 'none',
})

// ── Clip player ────────────────────────────────────────────────────────────────

export const videoWrapper = style({
  position: 'relative',
  background: '#000',
  borderRadius: vars.radius.md,
  overflow: 'hidden',
})

export const videoElement = style({
  width: '100%',
  display: 'block',
})

// ── Frame thumbnail strip ──────────────────────────────────────────────────────

export const thumbStrip = style({
  display: 'flex',
  gap: vars.space.xs,
  overflowX: 'auto',
  padding: `${vars.space.xs} 0`,
})

export const thumbItem = styleVariants({
  pending: {
    width: '40px',
    height: '30px',
    borderRadius: vars.radius.sm,
    border: `2px solid ${vars.color.borderDefault}`,
    cursor: 'pointer',
    flexShrink: 0,
    background: vars.color.bgCard,
  },
  annotated: {
    width: '40px',
    height: '30px',
    borderRadius: vars.radius.sm,
    border: '2px solid #43D186',
    cursor: 'pointer',
    flexShrink: 0,
    background: 'rgba(67,209,134,0.08)',
  },
  skipped: {
    width: '40px',
    height: '30px',
    borderRadius: vars.radius.sm,
    border: `2px solid ${vars.color.borderSubtle}`,
    opacity: 0.4,
    cursor: 'pointer',
    flexShrink: 0,
    background: vars.color.bgCard,
  },
  active: {
    width: '40px',
    height: '30px',
    borderRadius: vars.radius.sm,
    border: '2px solid #4FC3F7',
    cursor: 'pointer',
    flexShrink: 0,
    background: 'rgba(79,195,247,0.08)',
    outline: '2px solid rgba(79,195,247,0.3)',
    outlineOffset: '1px',
  },
})
