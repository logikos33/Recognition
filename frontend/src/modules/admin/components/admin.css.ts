/**
 * Admin module shared component styles — Vanilla Extract CSS-in-TS.
 */
import { style, styleVariants } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

// ── Page layout ─────────────────────────────────────────────────────────────

export const pageRoot = style({
  padding: vars.space.xl,
  maxWidth: '1200px',
})

export const pageHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: vars.space.xl,
})

export const pageTitle = style({
  fontSize: '20px',
  fontWeight: '700',
  color: vars.color.textPrimary,
})

export const pageSubtitle = style({
  fontSize: '13px',
  color: vars.color.textMuted,
  marginTop: vars.space.xs,
})

// ── Grid ─────────────────────────────────────────────────────────────────────

export const metricsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
  gap: vars.space.md,
  marginBottom: vars.space.xl,
})

export const twoColumn = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: vars.space.lg,
})

// ── Card ──────────────────────────────────────────────────────────────────────

export const card = style({
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.md,
  padding: vars.space.lg,
})

export const cardTitle = style({
  fontSize: '13px',
  fontWeight: '600',
  color: vars.color.textSecondary,
  marginBottom: vars.space.md,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
})

// ── MetricCard ────────────────────────────────────────────────────────────────

export const metricCard = style({
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderSubtle}`,
  borderRadius: vars.radius.md,
  padding: vars.space.lg,
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
})

export const metricIcon = style({
  color: vars.color.textMuted,
  flexShrink: 0,
})

export const metricValue = style({
  fontSize: '28px',
  fontWeight: '700',
  color: vars.color.textPrimary,
  lineHeight: 1,
})

export const metricLabel = style({
  fontSize: '12px',
  color: vars.color.textMuted,
  marginTop: '4px',
})

export const metricDelta = styleVariants({
  positive: { fontSize: '11px', color: vars.color.success, marginTop: '2px' },
  negative: { fontSize: '11px', color: vars.color.danger, marginTop: '2px' },
  neutral: { fontSize: '11px', color: vars.color.textMuted, marginTop: '2px' },
})

// ── Badge ─────────────────────────────────────────────────────────────────────

export const badge = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  padding: '2px 8px',
  borderRadius: vars.radius.full,
  fontSize: '11px',
  fontWeight: '600',
})

export const workerBadge = styleVariants({
  onpremise: [badge, {
    background: 'rgba(34,197,94,0.15)',
    color: vars.color.success,
  }],
  railway: [badge, {
    background: `rgba(234,179,8,0.15)`,
    color: '#ca8a04',
  }],
  offline: [badge, {
    background: `rgba(239,68,68,0.15)`,
    color: vars.color.danger,
  }],
})

export const roleBadge = styleVariants({
  superadmin: [badge, { background: 'rgba(168,85,247,0.15)', color: '#9333ea' }],
  admin:      [badge, { background: 'rgba(59,130,246,0.15)', color: '#2563eb' }],
  operator:   [badge, { background: 'rgba(34,197,94,0.15)',  color: '#16a34a' }],
  analyst:    [badge, { background: 'rgba(6,182,212,0.15)',  color: '#0891b2' }],
  trainer:    [badge, { background: 'rgba(249,115,22,0.15)', color: '#ea580c' }],
  viewer:     [badge, { background: 'rgba(107,114,128,0.15)',color: '#6b7280' }],
})

export const planBadge = styleVariants({
  basic:      [badge, { background: 'rgba(107,114,128,0.15)', color: '#6b7280' }],
  standard:   [badge, { background: 'rgba(59,130,246,0.15)',  color: '#2563eb' }],
  premium:    [badge, { background: 'rgba(168,85,247,0.15)',  color: '#9333ea' }],
  enterprise: [badge, { background: 'rgba(234,179,8,0.15)',   color: '#b45309' }],
})

export const statusBadge = styleVariants({
  open:           [badge, { background: 'rgba(59,130,246,0.15)',  color: '#2563eb' }],
  in_progress:    [badge, { background: 'rgba(249,115,22,0.15)', color: '#ea580c' }],
  waiting_client: [badge, { background: 'rgba(234,179,8,0.15)',  color: '#ca8a04' }],
  resolved:       [badge, { background: 'rgba(34,197,94,0.15)',  color: '#16a34a' }],
  closed:         [badge, { background: 'rgba(107,114,128,0.15)',color: '#6b7280' }],
})

export const priorityBadge = styleVariants({
  low:      [badge, { background: 'rgba(107,114,128,0.15)', color: '#6b7280' }],
  normal:   [badge, { background: 'rgba(59,130,246,0.15)',  color: '#2563eb' }],
  high:     [badge, { background: 'rgba(249,115,22,0.15)', color: '#ea580c' }],
  critical: [badge, { background: 'rgba(239,68,68,0.15)',  color: vars.color.danger }],
})

export const healthBadge = styleVariants({
  healthy:  [badge, { background: 'rgba(34,197,94,0.15)',  color: '#16a34a' }],
  degraded: [badge, { background: 'rgba(234,179,8,0.15)', color: '#ca8a04' }],
  critical: [badge, { background: 'rgba(239,68,68,0.15)', color: vars.color.danger }],
})

// ── Table ─────────────────────────────────────────────────────────────────────

export const table = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '13px',
})

export const th = style({
  padding: '8px 12px',
  textAlign: 'left',
  fontWeight: '600',
  color: vars.color.textMuted,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  whiteSpace: 'nowrap',
})

export const td = style({
  padding: '10px 12px',
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  color: vars.color.textPrimary,
  verticalAlign: 'middle',
})

export const trHover = style({
  ':hover': { background: vars.color.bgHover },
  cursor: 'pointer',
})

// ── Button ────────────────────────────────────────────────────────────────────

export const btn = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: vars.space.xs,
  padding: '6px 14px',
  borderRadius: vars.radius.sm,
  fontSize: '13px',
  fontWeight: '600',
  border: 'none',
  cursor: 'pointer',
  transition: 'opacity 0.15s',
  ':hover': { opacity: 0.85 },
  ':disabled': { opacity: 0.5, cursor: 'not-allowed' },
})

export const btnPrimary = style([btn, {
  background: vars.color.primary,
  color: '#fff',
}])

export const btnDanger = style([btn, {
  background: vars.color.danger,
  color: '#fff',
}])

export const btnGhost = style([btn, {
  background: 'transparent',
  color: vars.color.textSecondary,
  border: `1px solid ${vars.color.borderDefault}`,
}])

export const btnSuccess = style([btn, {
  background: vars.color.success,
  color: '#fff',
}])

// ── Input ─────────────────────────────────────────────────────────────────────

export const input = style({
  padding: '7px 10px',
  borderRadius: vars.radius.sm,
  border: `1px solid ${vars.color.borderDefault}`,
  background: vars.color.bgElevated,
  color: vars.color.textPrimary,
  fontSize: '13px',
  outline: 'none',
  ':focus': { borderColor: vars.color.primary },
})

export const select = style([input, { cursor: 'pointer' }])

// ── Alert banner ──────────────────────────────────────────────────────────────

export const alertBanner = styleVariants({
  info:        { background: 'rgba(59,130,246,0.1)',  borderLeft: '3px solid #2563eb', padding: `${vars.space.sm} ${vars.space.md}`, borderRadius: vars.radius.sm, marginBottom: vars.space.md },
  warning:     { background: 'rgba(234,179,8,0.1)',   borderLeft: '3px solid #ca8a04', padding: `${vars.space.sm} ${vars.space.md}`, borderRadius: vars.radius.sm, marginBottom: vars.space.md },
  danger:      { background: 'rgba(239,68,68,0.1)',   borderLeft: '3px solid #dc2626', padding: `${vars.space.sm} ${vars.space.md}`, borderRadius: vars.radius.sm, marginBottom: vars.space.md },
  maintenance: { background: 'rgba(249,115,22,0.1)', borderLeft: '3px solid #ea580c', padding: `${vars.space.sm} ${vars.space.md}`, borderRadius: vars.radius.sm, marginBottom: vars.space.md },
})

// ── Misc ───────────────────────────────────────────────────────────────────────

export const muted = style({ color: vars.color.textMuted, fontSize: '12px' })
export const mono = style({ fontFamily: vars.font.mono, fontSize: '12px' })
export const flex = style({ display: 'flex', alignItems: 'center', gap: vars.space.sm })
export const spacer = style({ flex: 1 })

export const dot = styleVariants({
  healthy:  { width: '8px', height: '8px', borderRadius: '50%', background: vars.color.success, display: 'inline-block' },
  degraded: { width: '8px', height: '8px', borderRadius: '50%', background: '#ca8a04', display: 'inline-block' },
  critical: { width: '8px', height: '8px', borderRadius: '50%', background: vars.color.danger, display: 'inline-block' },
})
